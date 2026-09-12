# Live latency correction — implementation, 2026-09-12

Status: deployed on **all six live streams**, after repeated cam3 validation.
The owner confirms audible phone playback at about two seconds of delay or
slightly less. Physical audio/video alignment was not explicitly confirmed.
Recording inputs and camera firmware settings are intact.

## Change

Retain the sample-count audio correction, but also reset the copied video's
timestamp origin with the FFmpeg `setts` bitstream filter:

```text
-bsf:v h264_metadata,setts=pts=PTS-STARTPTS:dts=DTS-STARTDTS -af asetpts=N/SR/TB
```

This does not re-encode video. The original input-probing defaults are retained;
aggressively shortening them failed to acquire usable camera video headers in
the preceding review. Details and isolated experiments are in
[the latency review](review-live-audio-latency.md).

Only go2rtc was restarted for this pilot. The Frigate camera key already existed,
so a Frigate/Tailscale restart was unnecessary. The full pre-change deployment
YAML was saved locally before editing; private backups are not published.

## Deployed cam3 validation

- 540 uniquely matched video frames: added NVR delay median 0.101 s, P95
  0.155 s, maximum 0.264 s, compared with 3.227 s median before the change.
- Fragmented MP4: 228 video frames at 1920x1080 plus 87 AAC frames, no errors.
- AAC and Opus: each decoded 20.000 seconds with nonzero signal and no errors;
  wall times 20.69 and 23.30 seconds including startup/probing.
- Source probe reconfirmed 8000 Hz mono PCM, 19.950 decoded seconds for a
  10-second request, no audio-only decoder errors.

These figures measure NVR processing delay and functional media output. They
do not certify camera-to-phone delay or physical audio/video synchronization.
Initial stream loading can still take several seconds while the input is
probed and a keyframe arrives. The existing intermittent reconnect issue has
not been declared solved.

## Verification package fixes

Fleet added-video-delay measurements after rollout:

| Camera | Median | P95 | Maximum |
|---|---:|---:|---:|
| cam1 | 0.102 s | 0.149 s | 0.371 s |
| cam2 | 0.103 s | 0.142 s | 0.288 s |
| cam3 (repeat) | 0.101 s | 0.155 s | 0.356 s |
| cam4 | 0.093 s | 0.268 s | 2.288 s |
| cam5 | 0.099 s | 0.215 s | 0.602 s |
| cam6 | 0.102 s | 0.132 s | 0.166 s |

All six passed the one-second P95 gate, but cam4 had 18 matched frames over
one second; transient stalls have not been eliminated. All six produced
playable fragmented MP4, AAC and Opus in successful checks. Cam2's initial
audio reconnects failed because its camera refused TCP connections to port
554 (confirmed in go2rtc logs); a targeted repeat passed all three checks.
This failure is preserved as evidence, not hidden by the passing repeat.

Later, cam6 briefly reported zero capture FPS and camera uptime around one
minute. No reboot was requested by this agent. It recovered to 5.1 FPS without
intervention. Whether another operator or the camera initiated the reboot was
not established at that point. The final sampled fleet was at 5.0–5.2 FPS,
with 0.3 skipped FPS on cam3 and zero on the others. Do not equate these
snapshots with uninterrupted recording or a completed reliability soak.

`verify-live-latency.py` compares identical decoded frames from the camera and
the live restream. It retains hashes and arrival times only, runs for 35 seconds,
excludes an initial eight-second warmup, requires at least 100 unique matched
frames and both readers to remain alive for the capture, and fails if the P95
added delay exceeds one second by default.

```sh
docker exec -i frigate python3 - cam3_kitchen < scripts/verify-live-latency.py
docker exec -i frigate python3 - cam3_kitchen 1920 1080 < scripts/verify-live-audio-any.py
```

Run the two sequentially to avoid adding unrelated diagnostic load. The delay
comparison itself opens one direct reference-camera connection plus a live
viewer. It requires recording input to remain a direct RTSP camera URL.
Like all WSL commands, it starts the distro and cannot assess idle availability.

`probe-camera-audio.py` now exits unsuccessfully with a null clock verdict if
audio is absent, capture fails/times out, audio decoding logs errors, samples
are invalid, or the capture is too short. Its audio capture requests only the
audio track, avoiding irrelevant mid-GOP video decoder warnings. Six regression
tests cover failure, missing audio, timeout, short capture and both normal and
half-speed valid clock measurements.

The sweep and repeat wrappers now honor verifier process failures even if a
PASS line was printed, retain failure diagnostics, and find their Python helper
relative to the checkout. The source-probe wrapper propagates failures; repeat
tests reject zero/invalid run counts. Mocked zero-run input exits 2 and all
changed shell scripts pass syntax checks.

## Remaining acceptance

Phone listening is confirmed at approximately two seconds or slightly less.
Still compare a physical clap or movement against sound/picture, including
other cameras, to verify synchronization and longer-term stability. Keep
initial-load time separate from ongoing stream latency.

If the phone still lags, inspect its actual active MSE/WebRTC transport and
buffer while it is playing. Do not assume the device is the cause, or change
Tailscale paths merely because the viewer is on Wi-Fi.

Rollback: remove `,setts=pts=PTS-STARTPTS:dts=DTS-STARTDTS` from the affected
live-stream source and restart go2rtc. Preserve the audio sample-count filter,
video framing filter, camera firmware settings and recording arguments.
