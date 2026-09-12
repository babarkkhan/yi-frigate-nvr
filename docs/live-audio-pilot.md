# Cam5 live listening pilot — 2026-09-12

Scope: live listening on `cam5_laundry`, using the existing stable camera
daemon. The owner confirmed audible live listening in Frigate on 2026-09-12.
Perceived latency, synchronization, and off-LAN playback remain unmeasured.
No speaker audio has been transmitted during this pilot.

## Implementation

Frigate 0.17.2 / bundled go2rtc 1.9.10. Cam5 is MStar y203c, hack 0.5.7,
`RTSP_ALT=alternative`, `RTSP_AUDIO=yes`. Its RTSP stream contains H.264
1920x1088 and mono L16/8000 microphone audio.

The named go2rtc stream matches the existing Frigate camera key. A single
FFmpeg input provides copied H.264 video, AAC for MSE, and Opus for WebRTC.
Only audio is transcoded. This FFmpeg source has no speaker backchannel.
The video bitstream is rewritten with `h264_metadata` without re-encoding.

Recording and detection still connect directly to the camera. While somebody
is viewing/listening, the pilot adds one camera connection. This deliberately
keeps the recording pipeline unchanged until the pilot passes. A later change
can move detection/recording to the local restream after stability validation.

## Measured audio timestamp fault

With the original timestamps, a ten-second FFmpeg pull from the camera took
20.22 seconds and decoded 19.982 seconds of samples. Plain go2rtc transcoding
also failed pacing: AAC produced 20 seconds in 41.81 wall seconds, while Opus
produced 39.914 seconds of samples for a requested 20 seconds and emitted
non-monotonic timestamp errors.

Adding `-af asetpts=N/SR/TB` to the live audio transcoder rebuilds its
timestamps from decoded sample count. In the initial audio-only validation:

| Codec | Decoded audio | Wall time | Decode errors | Signal RMS |
|---|---:|---:|---:|---:|
| AAC | 20.000 s | 20.97 s | 0 | -45.04 dBFS |
| Opus | 20.000 s | 20.71 s | 0 | -40.26 dBFS |

These are sequential samples, so RMS values are not a codec quality comparison.
The repeatable check passed again (AAC 20.95 s, Opus 20.80 s wall time for
20 seconds of decoded audio each). Recent completed recordings from all six
cameras fully decoded without errors during the pilot; their ages were 24–32
seconds. The four MStar recordings included AAC; Allwinner recordings were
video-only, consistent with the pre-existing state.

That audio-only result was insufficient: the direct go2rtc RTSP input produced
only 1,116 bytes of fragmented-MP4 headers in 12 seconds, with no playable
frames. Routing the pilot input through FFmpeg with `-c:v copy` and
`-bsf:v h264_metadata` produced 1,319,288 bytes, 174 decoded full-resolution
video frames and 69 AAC frames without decode errors in a follow-up sample.
The exact camera/go2rtc framing interaction is not isolated.

A chained AAC-to-Opus producer also showed intermittent RTP sequence errors
during repeated connection tests. The deployed pilot generates both audio
formats in the single camera-input FFmpeg process. The verification script
now checks actual fragmented-MP4 frames as well as audio pacing, so header-only
output cannot count as a successful live stream.

The single-producer validation passed: 1,422,379-byte fragmented MP4 with
192 video frames and 72 AAC frames; AAC and Opus each decoded 20 seconds
in 24.29 and 23.43 wall seconds respectively, with no errors. Both recordings
and tailnet access remained available. A subsequent repeated connection test
passed fragmented MP4 (252 video frames and 102 AAC frames) and AAC (20 seconds
in 23.72 wall seconds), but the Opus pull failed after 5.03 seconds with RTSP
DESCRIBE 404 and no audio. The cause of that intermittent startup/reconnect
failure remains open. The owner subsequently confirmed audible listening in
Frigate; the actual browser transport was not independently identified.
This establishes working listening, not production-proven reconnect stability.

Wall time includes connection/probing; it is **not** measured end-to-end audio
latency. Nonzero RMS proves signal, not intelligibility. Initial H.264 probing
can log missing PPS while joining mid-GOP; it subsequently identifies full
resolution. Existing MP4 framing workaround is preserved unchanged.

Run `docker exec -i frigate python3 < scripts/verify-live-audio.py` from the
deployment checkout to repeat the check. Audio-only samples stay in memory;
a short temporary MP4 is automatically deleted after decoding. It fails on
missing video, missing/silent audio, decode errors, or incorrect
pacing. It does not establish browser playback or WSL idle availability.

## Developer handoff and rollout readiness

**Ready for a staged MStar pilot; not ready for a blanket six-camera rollout.**
The owner requested that their developer own further deployment. Leave cam5
running with this configuration; do not expand it automatically.

1. Investigate the intermittent Opus DESCRIBE 404 above and repeat cold opens,
   refreshes, and reconnects. A speaker control disappearing as the feed loads
   was observed before audible listening was confirmed; check whether Frigate
   falls back to video-only jsmpeg. Do not count one successful pull as a fix.
2. Add one of cam1_mensroom, cam2_living, or cam4_hallway at a time. These are
   MStar cameras, but validate their actual audio tracks and timestamps before
   assuming cam5's correction is needed. Match each go2rtc name to its Frigate
   camera key and use that camera's RTSP URL. Keep recording inputs unchanged.
3. For each addition, verify audible room sound, repeated opens, measured delay,
   and continued fresh, playable recordings across all cameras. Check CPU load
   and camera FPS with simultaneous live viewers. The supplied verification
   script is deliberately cam5-specific; adapt its stream name and expected
   dimensions before applying it to another camera.
4. Handle cam3_kitchen and cam6_extra separately using the Allwinner findings
   below. They currently have no recorded audio track; copying cam5's go2rtc
   stanza cannot create a missing source track.
5. Listening is now confirmed, so the next speaker experiment can proceed with
   an observer present: a short 16 kHz S16LE mono clip uploaded as multipart.
   Confirm sound physically before selecting a live push-to-talk transport.

## Remaining acceptance checks

- Audible cam5 listening: **confirmed by owner**. Repeat after refresh and
  reconnect. Use the speaker control, or `M` on desktop. Low-bandwidth/jsmpeg mode
  has no audio. Frigate itself must reload the new config, not just go2rtc:
  its UI checks the in-memory `go2rtc.streams` configuration.
- Clap near the camera while another person listens remotely; record perceived
  delay and synchronization. Repeat from a real off-LAN phone on Tailscale.
- Continue checking fresh, playable recordings and per-camera FPS while viewing.
- Keep speaker tests gated on successful listening and an observer in the room.

## Allwinner investigation, separate from this pilot

Read-only checks confirmed both cam3 and cam6 have `RTSP_AUDIO=yes` and use
the alternative daemon. Allwinner 0.4.0 `system.sh` requests the PCM capture
FIFO only for explicit `pcm`, `alaw`, or `ulaw`, unlike MStar. This is a concrete
candidate explanation for the absent audio track; neither camera was changed.
Test an explicit codec on one Allwinner camera in a separate change, with a
recording baseline and rollback. Do not assume a config write alone starts the
capture path: it is initialized during camera startup.

## Speaker investigation, next stage

The existing `camera-speak.ps1` uses 8 kHz raw PCM based on an older wiki. The
MStar 0.5.7 playback page specifies S16LE, 16 kHz, 16-bit mono; its own upload
UI sends multipart form data. `speaker.sh` can incorrectly classify raw PCM
as multipart and strip it. The TinyALSA patch has a separate FIFO reader that
writes to playback, so the blanket claim that uploads require an active RTSP
backchannel is not established by the source.

Retest a short, correctly formatted clip with physical confirmation before
building live push-to-talk. Successful clip playback alone does not establish
a continuous low-latency speaker transport. Browser microphone capture will
also require HTTPS and a reachable WebRTC path over the tailnet.

## Rollback

Deployment required one Frigate restart so its in-memory config exposed the
stream to the UI. All six cameras resumed at approximately 5 fps. The tailnet
endpoint timed out after this restart; restarting the Tailscale sidecar restored
it. When restarting Frigate, verify the shared-namespace sidecar and actual
tailnet access afterward instead of assuming the startup dependency handles it.

Remove the `go2rtc` block added by this pilot from Frigate's main config and
restart go2rtc (or Frigate). Frigate recording inputs and camera firmware were
not changed. Do not replace unrelated later edits with a whole-file rollback.
The initial API experiment wrote to `go2rtc_homekit.yml`; that temporary entry
was removed and the file returned to its originally empty state. The main
Frigate YAML is the sole persistent source for this pilot.

## References

- [Frigate live audio](https://docs.frigate.video/configuration/live/)
- [Frigate go2rtc setup](https://docs.frigate.video/guides/configuring_go2rtc/)
- [Allwinner 0.4.0 initialization](https://github.com/roleoroleo/yi-hack-Allwinner/blob/0.4.0/src/static/static/home/yi-hack/script/system.sh)
- [MStar 0.5.7 playback format](https://github.com/roleoroleo/yi-hack-MStar/blob/0.5.7/src/www/httpd/htdocs/pages/speak.html)
- [MStar 0.5.7 speaker upload](https://github.com/roleoroleo/yi-hack-MStar/blob/0.5.7/src/www/httpd/cgi-bin/speaker.sh)
- [MStar 0.5.7 audio library](https://github.com/roleoroleo/yi-hack-MStar/blob/0.5.7/src/tinyalsa/Yihack_tinyalsa.patch)
