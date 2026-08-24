# NVR review and optimization - 2026-08-23

## Version: you are on the latest stable

    running : 0.17.2-3d4dd3a
    latest stable : v0.17.2  (2026-06-28)
    newer : v0.18.0-beta1/2/3 - PRERELEASE only

Nothing to upgrade. Do not move to 0.18 beta on a system you rely on; 0.17.x
config schema is stable and this stack is tuned for it.

Note the `stable-tensorrt` image cannot be version-pinned (upstream publishes
no per-version tensorrt tag), so a future `docker compose pull` will move you
forward whenever they cut a release. Record the running version before pulling.

## Boot persistence: confirmed working

    task    : HomeNVR-WSL-Keepalive
    trigger : MSFT_TaskBootTrigger        <- at boot, not logon
    runas   : <your-user> / S4U / Highest   <- no stored password
    state   : Running
    WSL     : Running

## Measured resource use

    detector inference : 7.4 ms   (RTX 4080 SUPER via ONNX/TensorRT)
    GPU                : 4-38% varying, decode 11-33%
    system CPU         : ~13%
    system memory      : ~29%
    shm                : 772 MB of 1 GB
    cameras            : 6/6 at 5 fps detect, 0 skipped frames

Enormous headroom. The 4080 is barely working.

## Changes made in this review

**shm_size 512mb -> 1gb.** Measured usage was 361 MB of 512 MB (71%), well
above what Frigate's formula predicts. Raising it revealed the buffers grow to
fill available space rather than having a fixed requirement, so this was less
urgent than it first looked - but headroom on shm is cheap (tmpfs commits only
what is used) and exhausting it crashes Frigate.

## Heavy features - all correctly off

    semantic_search   disabled
    face_recognition  disabled
    lpr               disabled
    audio detection   disabled
    genai             not configured

Only `birdseye` is on (default). It composites all six live views; harmless at
this load, disable if unused.

## Dual-stream: tested, works, deliberately NOT adopted

Now that `rtsp_server_yi` replaced the stalling `rRTSPServer`, `RTSP_STREAM:
both` works - cam6 served ch0_0 at 1920x1080 and ch0_1 at **640x360**
simultaneously. Frigate was reconfigured to detect on the substream and record
on the main stream, and soaked for 8 minutes: 6/6 cameras, zero errors.

**It was then reverted.** Reasons:

1. **It optimizes a constraint that does not exist.** GPU sits at 4-38% and
   CPU at 13%. Cutting decode load solves nothing here.
2. **It can reduce detection quality.** Detecting on the full-resolution stream
   lets Frigate crop regions at native resolution, which helps for small or
   distant people. A 640x360 detect stream throws that away permanently.
3. **It doubles RTSP connections per camera** - two streams instead of one -
   on hardware that was the source of every stability problem in this project.

cam6's camera-side `RTSP_STREAM: both` was left enabled and is harmless.

**When to revisit:** if cameras are ever added beyond six, or this moves to the
Beelink EQ14 where an N150 iGPU has far less decode headroom than a 4080. The
config change is documented in git history (see the reverted cam6 block).

## Storage

    media now      : 18 GB
    D: free        : 432 GB of 1.4 TB (69% used, mostly non-Frigate data)
    projected      : ~155 GB continuous at 2-day retention, plus event tiers

Comfortable. One caveat: Frigate sees the whole D: volume, so its storage
maintenance reasons about total free space, not a Frigate-specific budget. If
other data on D: grows large, they compete. Worth a glance at the 48-hour mark
to confirm retention actually prunes.

Recordings are on a **9p** mount (WSL -> Windows D:). That is the slow path,
but at ~0.9 MB/s aggregate it is nowhere near a limit - 0 skipped frames
confirms it.

## Suggested next steps, in value order

1. **Confirm retention prunes at 48 hours.** Everything else is verified; this
   is the one behaviour that has not yet had time to occur.
2. **Motion zones and masks.** cam1 and cam2 show detection firing constantly
   (det_fps 8.8 and 6.3 while others sit at 0). If that is scene noise rather
   than real activity, zones would cut wasted inference and false alerts.
   Requires looking at the actual camera views.
3. **Disable birdseye** if you never use the composite view.
4. **Camera health monitoring** - still the only real gap. The RTSP daemon
   problem is fixed, but nothing yet detects "HTTP answers, RTSP does not".
