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

It emits malformed **Access Unit Delimiter (NAL type 9)** and **Filler Data
(type 12)** units. They decode fine live, but break the Annex-B → AVCC
conversion when muxed into MP4:

```
Invalid NAL unit size (0 > 8246)
Error splitting the input into NAL units
```

In the browser that surfaces as
`CHUNK_DEMUXER_ERROR_APPEND_FAILED` and recordings simply will not play.
The Allwinner build is unaffected.

**Fix**, no re-encode and ~30% smaller files:

```
-bsf:v filter_units=remove_types=9|12
```

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

### 5. WSL2 will stop underneath you

`vmIdleTimeout=-1` in `.wslconfig` is **not sufficient** — measured, the distro
still stopped after ~100s idle, taking Docker and every container with it. A
long-running process inside the distro is required. See
`scripts/install-boot-task.ps1`.

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
        ├──► web UI on :5000
        └──► Tailscale Serve ──► https://<host>.<tailnet>.ts.net
                                 tailnet only, Funnel deliberately off
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
  install-boot-task.ps1       keep WSL alive across reboots
  camera-speak.ps1            push audio to a camera speaker
  make-speech.ps1             synthesise speech on the NVR
docs/                         the findings, in detail
```

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
