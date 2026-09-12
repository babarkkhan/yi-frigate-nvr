# Allwinner live-listening pilot: cam3 — 2026-09-12

Scope: cam3_kitchen only, Allwinner y20ga / yi-hack 0.4.0. Cam6 was not
modified. Speaker playback was not tested. The owner confirmed recognizable
room sound in Frigate on 2026-09-12. Ready for a staged cam6 rollout by the
developer, subject to the per-camera checks below.

## Camera change and evidence

Saved cam3's complete system-settings response, status, and the deployment's
Frigate configuration locally before the change. These backups are private and
are not included in this public repository. All six cameras had fresh, playable
recordings; cam3's baseline was H.264 1920x1080 without audio.

Changed exactly one camera setting using its normal HTTP configuration API:

```text
POST /cgi-bin/set_configs.sh?conf=system
{"RTSP_AUDIO":"pcm"}
```

Compared the full before/after settings and verified only RTSP_AUDIO changed
from `yes` to `pcm`. Kept `RTSP_ALT=alternative` and `RTSP_STREAM=high`.
Requested a camera reboot through `/cgi-bin/reboot.sh`; fresh uptime and a
subsequent settings read confirmed the reboot and persistent PCM selection.

Allwinner 0.4.0 startup requests the microphone FIFO for explicit `pcm`, `alaw`,
or `ulaw`; `yes` does not enter that branch. The firmware's own configuration
page offers those explicit codecs. After the change, cam3 advertised
`pcm_s16be`, 8000 Hz, mono. This supports the startup-setting explanation;
the internal FIFO state was not inspected on the camera.

## Timestamp measurement and Frigate configuration

The direct-camera probe requested 10 seconds and decoded 19.970 seconds of
audio over 20.23 wall seconds (decoded/requested 2.00; signal -57.82 dBFS).
Its audio timestamps therefore show the same half-speed behavior measured
on MStar. The initial H.264 probe emitted missing-PPS / no-frame messages while
joining the stream; those diagnostics are not being represented as a clean
whole-stream decode.

Added only this named live stream, leaving recording/detection inputs intact:

```yaml
go2rtc:
  streams:
    cam3_kitchen:
      - "ffmpeg:rtsp://192.168.3.3/ch0_0.h264#video=copy#audio=aac#audio=opus#raw=-bsf:v h264_metadata -af asetpts=N/SR/TB"
```

The sample-count filter corrects live audio pacing. Video is copied through
the same bitstream reserialization used by the MStar live streams; a separate
Allwinner ablation establishing whether that video filter is necessary was
not performed. One on-demand FFmpeg input supplies video, AAC, and Opus.

After the camera reboot, all six detection streams recovered to 5.0–5.1 fps,
with zero skipped FPS in the sampled status. All six recent completed recordings
decoded cleanly. Cam3 recordings now contain AAC/8000 without changing the NVR
recording arguments; cam6 remains video-only. Recording audio timing has not
been separately corrected or established as synchronized with video.

## Acceptance and developer handoff

Initial live verification passed: fragmented MP4 contained 187 H.264 frames
at 1920x1080 and 72 AAC frames (1,090,667 bytes). Corrected AAC decoded
20.000 seconds in 24.26 wall seconds, and Opus decoded 20.000 seconds in
23.40 wall seconds; neither had decode errors. Wall time includes startup
and probing and is not an end-to-end latency measurement.

A second verification after the Frigate restart also passed: fragmented MP4
had 159 video and 62 AAC frames; AAC and Opus each decoded 20.000 seconds in
23.79 and 23.80 wall seconds respectively, with no decode errors.

Frigate was restarted to expose cam3 in its UI, and the Tailscale sidecar was
restarted afterward. The in-memory config includes cam3 and actual tailnet
HTTP access was verified. An immediate post-restart FPS sample ranged from
4.7 to 5.0 across the fleet, with some other cameras reporting skipped frames;
cam3 reported 5.0 FPS and zero skipped frames. This is a short pilot, not a
long-duration stability result.

Use the generalized verifier directly; the existing shell wrappers have known
failure-propagation bugs documented in the review and must not gate rollout:

```sh
docker exec -i frigate python3 - cam3_kitchen 1920 1080 < scripts/verify-live-audio-any.py
```

It checks fragmented-MP4 frames, AAC and Opus pacing, and nonzero signal. It
does not prove intelligibility, browser transport, end-to-end latency, or WSL
idle availability. Running any command through WSL starts the distro.

Cam3 sound in Frigate is confirmed by the owner. All six recent recordings
decoded cleanly after the Frigate reload (ages 24.6–31.6 seconds); cam3's
sample included 200 video frames and 78 AAC frames. Still repeat opens
and reconnects and measure delay before declaring sustained reliability. The
existing intermittent live-audio startup/reconnect failure remains an open
system issue; passing a short cam3 pilot does not resolve it.

For cam6, save its own settings and recording baseline, apply `pcm` on that
camera and reboot, then measure its source codec and timestamps independently.
Only then add its matching stream with the measured correction, if needed.
Do not switch to the unstable standard RTSP daemon for this listening work.

## Rollback

Remove only the cam3 live-stream stanza. Restore cam3's RTSP_AUDIO to its saved
value (`yes` in this pilot), verify the write, and reboot that camera. This
returns it to the former video-only behavior. Preserve any unrelated changes.

Frigate must reload its main config for the UI to recognize a new stream.
After restarting Frigate, restart the shared-namespace Tailscale sidecar as
needed and verify actual tailnet HTTP access, as documented in the MStar pilot.

## Source references

- [Allwinner 0.4.0 startup](https://github.com/roleoroleo/yi-hack-Allwinner/blob/0.4.0/src/static/static/home/yi-hack/script/system.sh)
- [Allwinner 0.4.0 audio choices](https://github.com/roleoroleo/yi-hack-Allwinner/blob/0.4.0/src/www/httpd/htdocs/pages/configurations.html)
- [MStar pilot and known reconnect limitation](live-audio-pilot.md)
