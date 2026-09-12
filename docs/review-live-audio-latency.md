# Full live-audio rollout review and latency investigation — 2026-09-12

Reviewed public main `e3afde4` and the matching private deployment config.
No production configuration, camera setting, or service restart was performed
during this review. Experiments ran in a temporary go2rtc instance bound only
to container loopback, with separate API/RTSP ports and automatic cleanup.

## Main finding: the NVR adds seconds before the phone receives video

The owner reports both audio and video lag on Android and iPhone Chrome,
using home Wi-Fi with Tailscale and `http://home-nvr:5000/`. No numerical
phone delay was supplied. That URL bypasses the HTTPS Serve path previously
documented as slow. Home Wi-Fi does not itself bypass Tailscale.

Compared identical decoded video frames from cam3's direct camera RTSP stream
and its production go2rtc restream, timestamping their arrival on the same
host clock. Both readers used identical FFmpeg probing/decoding options.
Matched only frame hashes unique within each capture and excluded direct
frames from the first eight seconds. No video or microphone recording was
retained by this measurement.

| Test on cam3 | Matching frames | Median added video delay | Range | Media verification |
|---|---:|---:|---:|---|
| Current production pipeline | 483 | 3.227 s | 2.965–3.483 s | Existing pipeline |
| Isolated: 1 s probe, 32 KB probe size | 0 | unavailable | unavailable | Failed to acquire usable H.264 parameters; rejected |
| Isolated: 2 s probe, 1 MB probe size | 500 | 2.092 s | 1.886–2.409 s | Fragmented MP4, AAC and Opus passed |
| Isolated: reset video timestamp origin, original input defaults | 541 | 0.102 s | -0.003–4.249 s | Fragmented MP4, AAC and Opus passed |
| Same timestamp reset, repeat run | 539 | 0.101 s | -0.022–0.483 s | Fragmented MP4, AAC and Opus passed again |

These are relative delays introduced between two backend paths, **not**
camera-to-phone latency. Initial H.264 readers logged missing-PPS messages
while joining mid-GOP; only successfully decoded matching frames were compared.
Small negative values reflect measurement scheduling. The timestamp experiment
had an outlier, so the median alone must not be treated as a reliability claim.
The repeat run's 95th percentile was 0.167 s, with zero matched frames over
one second. Its later-half median was also 0.101 s. Startup remains separate:
the repeat's first decoded restream frame arrived at 5.827 seconds, versus
1.608 seconds on the direct reader; reducing steady delay does not eliminate
the camera keyframe and FFmpeg startup waits.

## Strong candidate: align the live video and audio timestamp origins

The deployed audio filter `asetpts=N/SR/TB` starts audio at zero. Video is
copied after input probing without an equivalent timestamp-origin reset.
The controlled test supports that origin mismatch as a major source of
buffering. The precise FFmpeg muxer queue behavior was not instrumented.

The candidate changes the live **video bitstream filter only**, retaining
video copy, the audio correction, AAC/Opus, and the original input defaults:

```yaml
go2rtc:
  streams:
    cam3_kitchen:
      - "ffmpeg:rtsp://192.168.3.3/ch0_0.h264#video=copy#audio=aac#audio=opus#raw=-bsf:v h264_metadata,setts=pts=PTS-STARTPTS:dts=DTS-STARTDTS -af asetpts=N/SR/TB"
```

This is a **tested candidate, not the deployed configuration**. The `setts`
bitstream filter adjusts packet timestamps without re-encoding the video.
The first candidate sample produced 228 video frames and 88 AAC frames in a
playable fragmented MP4. AAC and Opus each decoded 20.000 seconds in 24.36
and 23.66 wall seconds, with no decoder errors. Those wall times include
startup/probing and do not measure perceptual latency.
The repeat also passed: 227 video frames, 87 AAC frames, and 20.000 seconds
of decoded AAC/Opus in 24.31/23.81 wall seconds, with no decoder errors.

Next implementation should be a cam3-only pilot. Verify repeated cold opens,
audio/video synchronization and a timed physical action on both phones before
extending the change to other cameras. Resetting tracks separately can affect
their relative synchronization; matching video frames alone cannot certify
audio alignment. Keep the proven recording inputs unchanged during this test.
Rollback is removal of the added `setts` filter from that single stream.

## Rollout review findings

### P1: functional playback checks do not catch excessive live delay

The existing verifier decodes files and checks audio sample pacing, which is
useful but insufficient for live usability. It passed the pipeline that adds
3.23 seconds before phone playback. Keep these checks, but add a matching-frame
delay comparison and a physical phone audio/video check to rollout acceptance.

### P2: the documented contention diagnosis is not established

The README and cam6 rollout document promote an association into a cause:
failures rotating among cameras during sequential sweeps do not establish
resource contention or show that the number of configured streams causes it.
The producers are on demand; a sequential sweep is not a controlled concurrent
load experiment. A configured source entry also does not prove an active camera
connection. Each codec test can reuse a running producer, or cause a restart
after teardown; it does not necessarily add another concurrent camera connection.

The reviewed go2rtc logs also include a cam1 RTSP connection refusal and a
cam5 EOF. These may be different failure modes. Record the exact error,
producer lifetime, active consumers, camera uptime and load for failed runs
before selecting a cause. Preserve the documented intermittent reconnect issue
as unresolved. None of the isolated tests here proves it fixed fleet-wide.

### P2: failed source measurements can still appear to need no correction

`scripts/probe-camera-audio.py` still does not require successful ffprobe and
FFmpeg exit codes or an actual audio track before calculating `needs_asetpts`.
A failed pull with zero samples produces false instead of an invalid/unknown
result and can exit successfully. Fail the measurement explicitly and withhold
clock conclusions when audio is missing, decoding fails, or too little audio
is captured. Its caller also needs to propagate that failure.

### Remaining operational risks

- cam6 really is configured with `RTSP_STREAM=both`; the other five use `high`.
  Treat changing this as a separate measured test, not an explanation for delay
  shared by all cameras.
- Recording A/V synchronization is still unverified. Recent segment metadata
  on cam3/cam5/cam6 had audio start offsets of 0.168/0.361/0.051 s and broadly
  matching track durations. Metadata is not a physical synchronization test.
- Docker health checks make unhealthy containers visible but do not by themselves
  recover them. The documented WSL/Tailscale idle and restart failure modes
  still need independent monitoring. These WSL-backed checks wake the distro.
- Camera/server images use mutable `stable` tags. Preserve tested image digests
  when preparing an upgrade or rollback so deployment behavior is reproducible.

## Checks that passed

- All six live-stream names match the correct camera's recording input and
  expected dimensions; the published and deployed Frigate files match.
- MStar cameras remain on `alternative` with audio `yes`; both Allwinners use
  `alternative` with `pcm`. No camera was changed during this review.
- All six cameras sampled at 5.0–5.1 FPS with zero skipped FPS.
- All six recent completed recordings fully decoded, including AAC audio, with
  no errors; ages were 25.7–32.0 seconds.
- The revised sweep and repeat wrappers both returned exit 2 when Docker was
  mocked to fail. The former empty-list false-success bug is fixed. Repeat-test
  dimensions are now read from configuration rather than fixed to MStar's size.
- Tailscale reported Running and self-online; the host's tailnet HTTP request
  completed in 130 ms. This is not a phone-path bandwidth measurement.
- One Docker snapshot showed Frigate at 185% CPU (about 1.85 logical cores)
  within a 12-CPU WSL guest, with 4.2 GiB of 15.6 GiB memory used. This does not
  establish resource contention or eliminate transient load problems.

## Phone playback and WebRTC: next layer after the backend correction

No phone consumer was active during the backend snapshots, so its actual
transport, buffer depth and direct-versus-relayed Tailscale path were not
identified. Do not label the phone connection MSE or WebRTC from configuration
alone. Obtain a live sample while the phone is playing.

Frigate normally prefers MSE for configured go2rtc streams. The version 0.17.2
MSE player adapts buffering and handles iOS differently, including jumps toward
the live edge. That buffer is additional to the measured NVR delay.

The configuration publishes port 8555 but specifies no WebRTC candidates.
Frigate documentation recommends a reachable host candidate for local access
and the NVR's tailnet address for Tailscale. Automatic candidate discovery may
already work because the sidecar shares the network namespace; its absence
from YAML is not proof of a broken path. Verify actual ICE connectivity before
changing candidates. Do not expose ports publicly to solve a tailnet-only path.
WebRTC cannot remove seconds already accumulated upstream of go2rtc.

## Primary references

- [Reviewed rollout](https://github.com/babarkkhan/yi-frigate-nvr/commit/e3afde4)
- [FFmpeg setts bitstream filter](https://www.ffmpeg.org/ffmpeg-bitstream-filters.html#setts)
- [go2rtc 1.9.10 FFmpeg input defaults](https://github.com/AlexxIT/go2rtc/blob/v1.9.10/internal/ffmpeg/ffmpeg.go)
- [Frigate 0.17.2 MSE player](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/components/player/MsePlayer.tsx)
- [Frigate live-view configuration](https://docs.frigate.video/configuration/live/)
