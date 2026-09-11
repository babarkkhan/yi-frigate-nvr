# Tailnet throughput: Serve is ~12x slower than the raw port

Checked 2026-08-31, after being asked to confirm everything was broadcasting
over Tailscale. It is - and it is also far slower than it should be.

## Everything is reachable

Web UI, `/api/version`, `/api/config`, `/api/stats`, and a live JPEG from all
six cameras all return HTTP 200 with real bytes over the tailnet. Nothing is
missing or unregistered. The URL has not changed.

## But the UI takes ~3 minutes to load through Serve

The Frigate UI is about 2 MB of JavaScript and CSS:

| asset | size | LAN | tailnet via Serve | tailnet direct port |
|---|---|---|---|---|
| `main-*.js` | 645 KB | 0.004s | 55.2s | 5.2s |
| `index-*.js` | 1.18 MB | 0.018s | 102.4s | 8.7s |
| `index-*.css` | 152 KB | 0.003s | 12.0s | 0.7s |
| **total** | **~2 MB** | **0.03s** | **169.6s** | **14.5s** |

The HTML itself is tiny and arrives instantly, so the browser connects, shows
a blank page, and gives up before the bundle finishes. A 30-second recorded
clip behaved the same way: 3.19 MB in 2.3s on the LAN, versus a **timeout at
90s having transferred only 2.47 MB** through Serve.

## Why Serve specifically is slow

`tailscale0` counters showed only ~774 KB TX after several megabytes had been
pulled through Serve. Serve traffic does not traverse the kernel TUN device at
all - it is terminated inside `tailscaled` by **netstack**, Tailscale's
userspace TCP stack. Traffic to the node's own port goes through the kernel
path instead, and is roughly 12x faster.

## What was ruled out

Each of these was measured, not assumed:

| candidate | finding |
|---|---|
| DERP relay | no - `direct 192.168.3.148:41641` |
| latency | no - `tailscale ping` 1ms, five for five |
| MTU black hole | no - 1300B+ correctly returns "needs to be fragmented" |
| packet loss | no - zero errors/drops on `tailscale0` and `eth0` |
| CPU saturation | no - `tailscaled` 0-1%, system 82-92% idle |
| UDP GRO offload | no - `ethtool -K eth1 rx-udp-gro-forwarding on rx-gro-list off` changed nothing |
| docker bridge MTU 1280 | not in the path - tailnet traffic never crosses the bridge |

## Workaround

Use the port directly and skip Serve:

```
http://home-nvr:5000
```

`http://home-nvr.<your-tailnet>.ts.net:5000` and `http://100.64.0.10:5000` work
identically. This is plain HTTP, but it is inside the WireGuard tunnel - the
tailnet is already encrypted end to end, and the port is not exposed to the
internet. Serve's TLS is only wrapping an already-encrypted link.

## Unresolved, and the honest limit

Every measurement here was taken between the Windows host and a container on
**the same physical machine**. That traffic hairpins out through the Windows
Tailscale adapter, back into WSL's mirrored interface, and into the container.
It is entirely possible that loop is itself the reason the absolute numbers
are bad, in which case a genuinely remote client would see better figures.

What this does NOT affect is the **ratio**: Serve-versus-kernel-path is local
processing inside `tailscaled`, so the ~12x penalty should hold anywhere.

Settling the absolute numbers needs a second machine. The phone is the obvious
candidate - preferably on mobile data rather than home wifi, so it is genuinely
off-LAN. Until then, treat the absolute throughput figures as unconfirmed.

## On the LAN, none of this applies

`http://192.168.3.148:5000` runs at 2-4 MB/s and loads the UI in ~0.03s.

---

## Recurrence: tailscaled comes up with no UDP path after an unattended restart

Happened twice, six days apart - 2026-09-06 and 2026-09-12. Both times the
symptom was that the LAN worked perfectly and the tailnet was completely
unreachable:

```
LAN     http://192.168.3.148:5000    HTTP 200 in 0.03s
tailnet http://home-nvr:5000         TIMEOUT
tailnet https (Serve)                TIMEOUT
```

`netcheck` from inside the container:

```
* UDP: false
* IPv4: (no addr found)
* Nearest DERP: unknown (no response to latency probes)
```

The node reported *itself* offline, with `Tailscale cannot connect because the
network is down`, and flapped continuously - **240 `no-derp-connection` events
in two hours**, one roughly every 30 seconds.

Crucially `docker ps` said `Up 10 hours` throughout, and Frigate was entirely
unaffected: 6/6 cameras at 5 fps, because cameras are addressed by IP and need
no DNS or WAN path.

### Why it is a race, not a network fault

A plain `docker restart tailscale` fixed it both times, immediately and
completely - `UDP: true`, public endpoint acquired. Nothing about the host
network changed in between. What differs is *ordering*: on an unattended
restart the whole stack comes up at once, and on a manual restart Frigate's
network namespace already exists.

`tailscale` runs with `network_mode: service:frigate`, so Frigate owns the
namespace. The old config used:

```yaml
depends_on:
  - frigate
```

which waits only for the container to **start**, not to be usable.

### Fix

```yaml
depends_on:
  frigate:
    condition: service_healthy
```

Compose now blocks correctly on startup - `frigate Waiting` → `frigate
Healthy` → `tailscale Starting`.

A healthcheck was added alongside it, because the worst part of both incidents
was invisibility:

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:9002/healthz >/dev/null 2>&1 || exit 1"]
  interval: 60s
  start_period: 60s
```

`/healthz` on port 9002 comes from `TS_ENABLE_HEALTH_CHECK` and returns 503
when tailscaled considers itself unhealthy. `docker ps` now shows
`(unhealthy)` instead of a contented `Up 10 hours`.

**This makes the failure visible and less likely; it does not make it
self-healing.** Docker does not restart a container for being unhealthy. If it
recurs despite the ordering fix, something has to act on that unhealthy state.

### Verified after the fix

```
LAN     :5000                        HTTP 200  0.06s
tailnet http://home-nvr:5000         HTTP 200  0.57s
tailnet https Serve                  HTTP 200  0.60s
all six live frames over the tailnet HTTP 200  0.7-2.4s each
tailscale container                  Up (healthy)
```
