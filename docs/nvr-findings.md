# NVR bring-up findings - 2026-08-22

Stack is running: **6/6 cameras streaming and recording**, Frigate 0.17.2 on
this PC via WSL2 Ubuntu 26.04 + Docker 29.7.2.

Three problems were hit. Two were real bugs, one was mine.

## 1. Frigate crash-loops when a camera probe times out (upstream bug)

    File "/opt/frigate/frigate/util/services.py", line 735, in probe_with_ffprobe
        except (json.JSONDecodeError, ValueError, KeyError, asyncio.SubprocessError):
    AttributeError: module 'asyncio' has no attribute 'SubprocessError'

`asyncio.SubprocessError` does not exist. When Frigate probes a camera to
auto-detect its resolution and that probe times out, the **exception handler
itself raises**, killing the process. With six fragile cameras this produced a
permanent crash loop and a 3-minute startup before the API even answered.

**Fix:** set `detect.width` / `detect.height` explicitly on every camera so
Frigate never probes. Startup went from ~3 minutes to 10 seconds.

This is an upstream defect in 0.17.2 and worth reporting.

## 2. Recording fails on any camera with PCM mu-law audio

    [mp4] Could not find tag for codec pcm_mulaw in stream #1,
          codec not currently supported in container
    [out#0/segment] Could not write header (incorrect codec parameters ?)

MP4 cannot carry PCM mu-law. `preset-record-generic-audio-copy` therefore makes
the **entire ffmpeg process die**, so the camera never streams at all - the
failure looks like a connection problem, not an audio problem.

The four MStar y203c cameras emit PCM mu-law. The two Allwinner y20ga cameras
have no audio track. That is exactly why 2/6 worked and 4/6 did not.

**Fix:** `record: preset-record-generic-audio-aac`. Transcodes 64 kbps mono
mu-law to AAC. Negligible cost, audio preserved.

### How this was nearly missed

An early hypothesis correctly guessed audio, but the test that "disproved" it
wrote to **mpegts**, which *does* support PCM mu-law. It passed, and audio was
wrongly ruled out. Frigate writes **mp4**. The container format was the whole
difference. Test with the same muxer as production.

## 3. go2rtc removed - it was not buying anything

The original design used go2rtc to pull each camera once and share the stream
between detect and record. But because both roles sit on a **single input**,
Frigate already opens exactly one connection per camera. go2rtc added a layer
that was timing out (`i/o timeout` reading from the cameras) for no benefit.

Cameras now point directly at `rtsp://<ip>/ch0_0.h264`.

Trade-off accepted: live view in the UI falls back to jsmpeg instead of WebRTC.
If WebRTC is wanted later, reintroduce go2rtc - but only after confirming it
can hold all six of these cameras.

## Confirmed working

    6/6 cameras streaming at 5 fps detect
    recordings written for all six, ~100 mp4 segments in the first minutes
    nvidia hwaccel auto-detected and in use: GPU decode at 18%
    system CPU ~0%, memory 19%
    detector: CPU, 15.8 ms inference
    zero errors in steady state

## Environment notes

- WSL2 Ubuntu 26.04 (`resolute`). Docker publishes packages for it.
- `nvidia-ctk runtime configure` rewrites `/etc/docker/daemon.json` but the
  daemon must be **restarted** afterwards or `--gpus all` silently fails. The
  setup script's original GPU test failed for exactly this reason.
- WSL eth0 MTU is 1420. Forcing RTSP over TCP avoids any UDP fragmentation
  concern.
- NordVPN was NOT a problem - all six cameras were reachable from WSL.

## Still to do

- [ ] Switch detection to the RTX 4080: `scripts/build-yolo-model.sh`, then
      swap the detector block. GPU already handles decode; only inference is
      still on CPU.
- [ ] Verify a person detection actually fires and an alert clip is written.
- [ ] Confirm 2-day retention prunes correctly once past 48h.
- [ ] Camera health monitoring - RTSP daemons die silently while HTTP keeps
      answering (see rtsp-stability.md).
