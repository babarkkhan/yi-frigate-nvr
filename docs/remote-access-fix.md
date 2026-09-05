# Tailscale / remote access outage - root cause and fix, 2026-08-26

Symptom: Frigate would not load. Small API calls worked, the actual UI never
appeared. Also affected: `http://192.168.3.148:5000` had never worked at all
from another device on the LAN.

Frigate itself was healthy throughout - 6/6 cameras, container up 11 hours,
zero errors. The whole problem was in how it was being reached.

## Three separate faults, found in order

### 1. Tailscale Serve was proxying to the wrong place

    netstack: could not connect to local backend server at 127.0.0.1:5000:
    dial tcp 127.0.0.1:5000: connect: connection refused

`serve.json` said `"Proxy": "http://frigate:5000"`, and `tailscale serve
status` echoed that back happily. But **Tailscale Serve only proxies to
localhost.** Given a hostname it ignores it and dials 127.0.0.1 inside its own
container, where nothing listens.

Fix: `network_mode: service:frigate` on the tailscale container, so it shares
Frigate's network namespace and `127.0.0.1:5000` genuinely is Frigate. The
serve target became `http://127.0.0.1:5000`.

Note `hostname:` cannot be set alongside a shared namespace - the tailnet name
moves to `TS_HOSTNAME`.

### 2. An MTU black hole, disguised as a TLS failure

After fix 1, HTTPS still timed out, with:

    http: TLS handshake error from 100.64.0.11: EOF

which looks like a certificate problem. It was not. Forcing a fresh
certificate changed nothing. The discriminating test was plain HTTP:

    small response (14 B)    -> HTTP 200 in 0.09s
    large response (6.8 KB)  -> timed out, 0 bytes received
    ping 1200B (DF)          -> 100% loss
    ping 1400B (DF)          -> "Packet needs to be fragmented but DF set"

Nothing to do with TLS. **Anything above roughly 1200 bytes was being silently
dropped.** A TLS handshake sends a ~4.8 KB certificate chain, so it was simply
the first thing large enough to notice.

Cause: WSL2's NAT interface has an MTU of 1420 while Docker bridges default to
1500. Packets sized for 1500 die crossing that boundary, and no ICMP gets back
to trigger path-MTU discovery.

### 3. Container ports were never reachable on the LAN

    LocalAddress  LocalPort
    ::1           5000
    127.0.0.1     5000

Under WSL2's default NAT networking, published container ports are relayed to
Windows **localhost only**. `http://192.168.3.148:5000` worked from the PC
itself and from nowhere else. The setup notes claiming otherwise were wrong.

## The fix for 2 and 3: WSL mirrored networking

Both are consequences of WSL sitting behind its own NAT. Setting
`networkingMode=mirrored` in `.wslconfig` removes that boundary - WSL shares
the Windows network interfaces directly.

    [wsl2]
    vmIdleTimeout=-1
    networkingMode=mirrored

    [experimental]
    hostAddressLoopback=true

After a `wsl --shutdown`, WSL sees the real interfaces:

    eth1  192.168.3.148/24     <- the LAN address itself
    eth4  100.64.0.11/32   <- the Tailscale interface
    mtu   1500

## Verified after the fix

    http://127.0.0.1:5000/api/version        HTTP 200
    http://192.168.3.148:5000/api/version    HTTP 200   <- now works from any LAN device
    https://home-nvr.<tailnet>.ts.net/api/version   HTTP 200 in 0.81s
    https://home-nvr.<tailnet>.ts.net/              HTTP 200, 6833 bytes in 1.1s
    ping -l 1200 over tailnet                Reply, 1-3ms

Six-minute soak afterwards: 6/6 cameras every minute, zero frame failures.

## What this should have caught earlier

When Tailscale was first set up, `tailscale serve status` showed the right
config and the certificate was issued, and that was treated as success. It was
not tested by actually fetching a page - noted at the time as untested, but the
implication was understated. Configuration that reports itself as correct is
not the same as a working request.

Also worth remembering: `TLS handshake error` was a red herring pointing at
certificates. The one test that broke it open was trying the same request
over plain HTTP - removing TLS from the picture entirely.

## Also of note

Both phones were showing `offline, last seen 1-2h ago` on the tailnet. Even
with the server side fixed, the Tailscale app has to be connected on the
device you are viewing from.
