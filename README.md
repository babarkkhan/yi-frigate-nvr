# Yi cameras → local Frigate NVR

Six Yi cameras taken off the vendor cloud and onto a local, GPU-accelerated
[Frigate](https://frigate.video) NVR, reachable remotely over Tailscale with
nothing exposed to the public internet.

This repo is the working configuration **plus the findings** — including three
firmware bugs that cost real time to isolate. If you are doing the same thing,
the `docs/` folder is the valuable part.

---

## The findings, up front

If you only read one thing, read this. All of it was measured, not assumed.

### 1. `rRTSPServer` stalls; `rtsp_server_yi` does not

yi-hack ships three RTSP implementations, selected by `RTSP_ALT` in
`system.conf`. The default one **freezes after ~100 seconds** while the camera
stays perfectly healthy — uptime climbing, memory flat, load normal.

| `RTSP_ALT` | daemon | streaming |
|---|---|---|
| `standard` (default) | `rRTSPServer` | **stalls** |
| `alternative` | `rtsp_server_yi` | solid |
| `go2rtc` | go2rtc | needs the binary on an SD card |

Symptom in Frigate: *"No frames have been received"*, rotating between cameras.
Switching to `alternative` took 1,953 frame failures in 8 minutes down to **0**.

### 2. The MStar build of `rtsp_server_yi` corrupts MP4 recordings

The stream decodes cleanly live, but breaks the Annex-B → AVCC conversion when
muxed into MP4 — **780 errors** in one 20-second segment:

```
Invalid NAL unit size (0 > 11093)
Error splitting the input into NAL units
```

In the browser that surfaces as `CHUNK_DEMUXER_ERROR_APPEND_FAILED` and
recordings simply will not play. The Allwinner build is unaffected
(`nb_read_frames=400`, 0 errors).

**Fix** — any bitstream re-serialisation, no re-encode:

```
-bsf:v filter_units=remove_types=9|12
```

**Why it works is not what it looks like.** An earlier version of this README
claimed the cause was malformed AUD (type 9) and Filler (type 12) NAL units.
**That was wrong** — neither type is present in the stream at all. Ablation on
the same file, changing only the filter:

| bitstream filter | NAL errors |
|---|---|
| none | **780** |
| `filter_units=remove_types=9\|12` | 0 |
| `filter_units=remove_types=99` — a type that **does not exist** | 0 |
| `h264_metadata` — removes nothing | 0 |

A filter that removes nothing fixes it. The defect is in output **framing**;
`remove_types` is inert. Zero-length NALs and malformed SEI were both ruled out
by measurement, and the root cause is **not isolated** — see
`docs/recording-corruption.md` and upstream
[issue #593](https://github.com/roleoroleo/yi-hack-MStar/issues/593).

### 3. Two-way audio requires the daemon that stalls

Only `rRTSPServer` advertises the ONVIF audio backchannel. Proof, same camera,
same config, only the daemon swapped:

```
rtsp_server_yi                    rRTSPServer
m=video  track0                   m=video  track1
m=audio  track1  (mic)            m=audio  track2  (mic)
                                  m=audio  track3
                                    a=sendonly     <- backchannel
```

`rtsp_server_yi` accepts the `-b` flag without complaint and never advertises
the track. So on MStar hardware you can have **stable streaming or two-way
audio, not both**.

### 4. Frigate 0.17.2 crash-loops when a camera probe times out

```python
except (json.JSONDecodeError, ValueError, KeyError, asyncio.SubprocessError):
AttributeError: module 'asyncio' has no attribute 'SubprocessError'
```

`asyncio.SubprocessError` does not exist, so the exception handler itself
raises. Workaround: set `detect.width` / `detect.height` explicitly so Frigate
never probes. Startup went from ~3 minutes to 10 seconds.

### 5. WSL2 will stop underneath you, and the keepalive needs two triggers

`vmIdleTimeout=-1` in `.wslconfig` is **not sufficient** — measured, the distro
still stopped after ~100s idle, taking Docker and every container with it. A
long-running process inside the distro is required.

But a keepalive registered with **only an AtStartup trigger is a trap.** Any
`wsl --shutdown` kills it with exit code 1, and nothing re-runs it until
Windows next reboots. Measured: the keepalive sat dead for over 24 hours while
WSL tore the distro down every 30–60 seconds, restarting Docker, Frigate and
Tailscale each time. Remote clients saw `ERR_CONNECTION_ABORTED`.

`scripts/install-boot-task.ps1` therefore registers **boot + a 5-minute repeat**
with `MultipleInstances=IgnoreNew`, so the repeat never double-starts a healthy
keepalive and revives a dead one within 5 minutes.
`scripts/harden-keepalive.ps1` applies the same fix to an existing task.

The healthy steady-state `LastTaskResult` is **`2147946720`** (`0x800710E0`,
"the operator or administrator has refused the request") — that is the repeat
trigger being correctly declined. The failure signature is **`State: Ready`
with result `1`**.

### 6. Tailscale Serve is ~12x slower than the node's own port

Everything is reachable over the tailnet, but the ~2 MB Frigate UI bundle takes
**169s through Serve versus 14.5s hitting the port directly**, and a 30-second
clip times out entirely. The page connects, renders blank, and the browser
gives up.

Serve is terminated by **netstack**, Tailscale's userspace TCP stack, and never
touches the kernel TUN — `tailscale0` showed only 774 KB TX after several MB
had gone through Serve.

Use the port instead, still inside WireGuard and still encrypted end to end:

```
http://home-nvr:5000
```

Ruled out by measurement: DERP relay (direct, 1 ms), MTU black hole, packet
loss, CPU, and UDP GRO offload. See `docs/tailnet-throughput.md` — including
the caveat that these figures were taken between two endpoints on the same
physical machine.

### 7. An NVIDIA driver update breaks the GPU inside a running WSL distro

`/usr/lib/wsl/lib` is bind-mounted from Windows at distro boot and never
re-mounts. After a driver update the distro keeps the **old** userspace driver
while Windows moves on, and containers fail in the NVIDIA prestart hook:

```
nvidia-container-cli: WSL environment detected but no adapters were found
```

`/dev/dxg` is still present and the GPU is fine — the mount is stale. Fix:
`wsl --shutdown`, then restart. Nothing recovers from this automatically:
`restart: unless-stopped` cannot help a container that fails before its process
exists, and the keepalive above actively preserves the stale mount.

A related failure: ffmpeg losing its CUDA context (`cu->cuInit(0) failed`)
while `nvidia-smi` stays perfectly healthy. A container restart clears it.

---

## Identifying your cameras before flashing

The serial prefix alone is **not** enough — `BFUS` appears in supported rows of
two different projects. The **firmware version** is what decides:

| Firmware starts | Platform | Project |
|---|---|---|
| `4.x` | MStar | [yi-hack-MStar](https://github.com/roleoroleo/yi-hack-MStar) |
| `9.x` / `11.x` / `12.0` / `12.1` | Allwinner | [yi-hack-Allwinner-v2](https://github.com/roleoroleo/yi-hack-Allwinner-v2) |
| `12.2.0*` | Allwinner (y20ga) | [yi-hack-Allwinner](https://github.com/roleoroleo/yi-hack-Allwinner) |

Note the third row: **`yi-hack-Allwinner` is not obsolete.** It covers a
different model (y20ga), not an older generation of the same one. Assuming the
`-v2` project superseded it leads to the wrong package and a silent failure.

Three independent signals agreed on every camera here — MAC vendor OUI, serial
body, and firmware version. See `docs/cameras.md` and `docs/bfus-decision.md`.

---

## What is running

```
6 Yi cameras (yi-hack, cloud disabled, ports 80+554 only)
        │  RTSP, one connection each
        ▼
   Frigate 0.17.2  ── detect + record on a single stream per camera
        │              ONNX/TensorRT on an RTX 4080, ~6-8 ms inference
        │              2-day continuous, 14d alerts, 7d detections
        ├──► web UI on :5000                    LAN, full speed
        ├──► http://<host>:5000 over the tailnet  PREFERRED remote path
        └──► Tailscale Serve ──► https://<host>.<tailnet>.ts.net
                                 tailnet only, Funnel deliberately off
                                 works, but ~12x slower - see finding 6
```

Host is Windows + WSL2 (Ubuntu) + Docker. It ports to a plain Linux box with
three edits — see the end of `docs/nvr-setup.md`.

Measured: **1.19 Mbps** per camera, ~12.8 GB/camera/day, ~155 GB for six at
2-day retention.

---

## Layout

```
compose.yaml                  Frigate, NVIDIA GPU
compose.tailscale.yaml        opt-in remote access overlay
services/nvr/config/          Frigate config.yml
services/tailscale/           Tailscale Serve config
secrets/*.example             copy to *.env, gitignored
scripts/
  prime-sd.ps1                write firmware to an SD card, verified by SHA-256
  configure-cam.ps1           post-flash camera config, dry-run by default
  setup-wsl-docker.sh         Docker + NVIDIA Container Toolkit inside WSL
  build-yolo-model.sh         export the YOLOv9 ONNX model Frigate needs
  install-boot-task.ps1       keep WSL alive (boot + 5-minute repeat trigger)
  harden-keepalive.ps1        add the repeat trigger to an existing task
  camera-speak.ps1            push audio to a camera speaker
  make-speech.ps1             synthesise speech on the NVR

  # health checks - all read-only, safe to run any time
  nvr-status.sh               per-camera fps, detector ms, GPU; ALL OK or names
                              the stalled cameras
  probe-rtsp.sh               what each camera's RTSP actually declares -
                              catches the width=0 wedge
  verify-recordings.sh        fully decodes the newest segment per camera
  last-recording.sh           newest segment per camera, and how long ago
  retention-report.sh         recorded footage per day
  tailnet-broadcast-check.sh  every endpoint over the tailnet, with timings

  # tooling for upstream issue #593
  repro-593.sh                reproduce the MP4 corruption
  bsf-ablation.sh             which bitstream filter actually fixes it
  nal-analysis.py             NAL census of an Annex-B capture
  nal-trailing.py             zero-length NALs and trailing-zero padding
  nal-empty-context.py        byte context around empty NAL units
  sei-parse.py                SEI internal length fields
docs/                         the findings, in detail
```

**A warning about the health checks.** `nvr-status.sh` and friends are run via
`wsl -d Ubuntu -- ...`, and **each such command starts the distro**. If the
distro is down, the probe silently repairs the very fault it is measuring. An
8-minute soak once reported 7/8 "ALL OK" for exactly this reason, while a phone
found the system unreachable on the first try. To measure availability
honestly, use `curl` from the Windows host or a real client and touch WSL zero
times — that is what `tailnet-broadcast-check.sh` does.

---

## Getting started

1. **Identify every camera** — serial prefix *and* exact firmware version.
   Match both against the tables in `docs/cameras.md`. If a camera does not
   match a row, stop.
2. **Do not let the cameras update.** Newer firmware may have no hack path and
   there is no documented downgrade.
3. Flash a spare camera first. `scripts/prime-sd.ps1` refuses anything that is
   not FAT32 and empty, and verifies every file by SHA-256 after copying.
4. `scripts/setup-wsl-docker.sh`, then `docker compose up -d`.
5. Start on the CPU detector, prove the pipeline, then build the ONNX model and
   switch to the GPU.

Full sequence in `docs/nvr-setup.md`.

---

## Notes

IP addresses, camera names and hostnames throughout are from a working setup
and are meant to be replaced. Camera serials are redacted to their platform
prefix (`BFUSY21` = MStar, `BFUSY31` = Allwinner) — that prefix is the
diagnostically useful part.

Flashing custom firmware can brick a camera. Everything here worked on six
cameras with no failures, but the matching has to be exact. The upstream
projects say it plainly: *do not use a firmware on an unlisted model*.

## Credit

All the hard firmware work belongs to
[roleoroleo](https://github.com/roleoroleo) and the yi-hack contributors, and
to [blakeblackshear](https://github.com/blakeblackshear) for Frigate. This repo
is just a configuration and a set of notes.
