# Camera dropouts - RESOLVED, 2026-08-23

Symptom: Frigate reporting "No frames have been received", rotating between
cameras.

## Root cause: rRTSPServer, the hack's default RTSP daemon

**Not the hardware.** The cameras stream fine in the Yi Home app, which was the
observation that redirected this investigation - and it was correct.

Instrumenting cam1 while pulling its stream showed exactly what happens:

    t      uptime   load              freemem   bytes captured
     10s   20694    2.29 2.05 2.04    15740     1,572,864
     50s   20746    2.03 2.01 2.03    16432     9,437,184
     90s   20797    2.42 2.13 2.07    15764     16,777,216
    100s   20809    2.36 2.13 2.07    16420     17,958,888
    110s   20821    2.52 2.17 2.09    16376     17,958,888   <- frozen
    120s   20832    2.72 2.23 2.11    16372     17,958,888   <- frozen

The stream froze at 100 seconds while:
- **uptime kept climbing** - the camera did not reboot
- **free memory stayed flat** at ~16 MB - not memory exhaustion
- **load stayed normal** at ~2.0-2.7 - not CPU starvation

So the camera was healthy and simply stopped sending. That is a fault in
`rRTSPServer`, the RTSP daemon yi-hack runs by default. The Yi app never uses
it, which is why the app was unaffected.

## Fix: RTSP_ALT = alternative

yi-hack ships three RTSP implementations, selected by `RTSP_ALT` in
system.conf (see `script/service.sh`):

| RTSP_ALT | daemon | notes |
|---|---|---|
| `standard` (default) | `rRTSPServer` | **stalls** - the bug |
| `alternative` | `rtsp_server_yi` | **works** |
| `go2rtc` | `go2rtc` | needs the binary on an SD card; not usable here, the cameras run cardless |

Applied to all six cameras and rebooted.

## Evidence

cam1, sole client, 5-minute pull (~6000 frames expected at 20fps):

    rRTSPServer   froze at 100s
    rtsp_server_yi   6009 frames, steady throughout, zero stalls

All six concurrently for 5 minutes, *while Frigate was also streaming* (so two
clients per camera):

    cam2  6004   cam3  6002   cam4  5675
    cam5  5686   cam6  5213   cam1  4958

Against the earlier sole-client baseline on rRTSPServer, where cam1 managed 240
frames and cam5 managed 425, that is a transformation.

## What was wrong in the earlier analysis

The previous conclusion - "these SoCs cannot sustain continuous 1080p20 RTSP" -
was wrong. It was inferred from the failure pattern without testing the
alternative daemon. The hardware was never the limit.

## Changes retained from the earlier work

These are still worth having; they make any future dropout cheaper:

| Change | Reason |
|---|---|
| `-timeout` 10s -> 30s | a brief stall no longer tears down ffmpeg |
| `retry_interval` 10s -> 3s | faster recovery when a teardown does happen |
| `record: preset-record-generic` | AAC transcode fought non-monotonic DTS in the mu-law audio |
| `RTSP_AUDIO: no` (MStar) | removes the broken audio track at source |
| `SAVE_VIDEO_ON_MOTION: no` | cameras were doing their own motion recording - wasted work |

Note the audio ones remain justified independently: the DTS problem was real
and separate from the daemon stall. Recordings currently carry no audio.

---

## Audio re-test, 2026-08-23 (after the daemon fix)

Audio was disabled earlier because the AAC encoder fought non-monotonic DTS in
the `pcm_mulaw` track. With `rtsp_server_yi` the audio path changed, so it was
worth retesting.

**The codec is different under the alternative daemon:**

    rRTSPServer      -> pcm_mulaw    (broken DTS, destabilised ffmpeg)
    rtsp_server_yi   -> pcm_s16be    8000 Hz mono

Test on cam5_laundry only, via a per-camera `output_args` override, 8 minutes:

    6/6 cameras streaming, every minute
    DTS / audio problems : 0
    frame failures       : 0

Recorded segment verified:

    cam5_laundry/07.48.mp4   0,h264,video   1,aac,audio,8000,1   <- audio present
    cam2_living/07.56.mp4    0,h264,video                        <- control

Size cost is negligible: 1424 KB vs 1390 KB for a comparable segment, ~2%.

**Conclusion: audio is safe to re-enable.** The DTS problem was a symptom of
rRTSPServer, not an independent fault - the earlier reasoning attributed it to
the mu-law codec itself, which was wrong.

To roll out fleet-wide: set `RTSP_AUDIO: yes` on cams 1, 2 and 4, change the
global `record` back to `preset-record-generic-audio-aac`, and drop the
per-camera override on cam5. The Allwinner cameras (3, 6) have no audio track
at all, so they are unaffected either way.
