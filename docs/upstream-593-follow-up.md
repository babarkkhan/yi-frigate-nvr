# Issue 593: direct RTP evidence and SEI-skip comparison, 2026-09-19

The maintainer's [September 16 response](https://github.com/roleoroleo/yi-hack-MStar/issues/593#issuecomment-5702252678)
requested a raw RTP capture and suggested the grabber's `-s` option. Both were
tested on one MStar y203c camera running firmware 0.5.7, using the alternative
RTSP daemon. Production recording filters were retained throughout.

## Result

**The corruption still reproduces. Camera-side `-s` avoids it in this short
test, but does not make the observed RTP framing conformant.** Removing `-s`
reproduced the corruption again. No persistent camera or Frigate change was
retained; this is diagnostic evidence, not a fleet rollout recommendation.

Each phase used one FFmpeg 7.0 RTSP/TCP connection with three video-only MP4
outputs, each requesting 12 seconds. The outputs within a phase shared their
source. Different phases were separate live captures, so frame counts differ.
`ffprobe -count_frames -v error` decoded each output. Error counts below count
diagnostic messages, not distinct damaged frames; ffprobe's exit code alone
was zero even on the corrupt files.

| Grabber | MP4 output | Decoded frames | Invalid NAL-size messages | Split-NAL messages |
|---|---|---:|---:|---:|
| Normal | Stream copy, no filter | 6 | 422 | 221 |
| Normal | `filter_units=remove_types=99` | 207 | 0 | 0 |
| Normal | `h264_metadata` | 207 | 0 | 0 |
| `-s` | Stream copy, no filter | 206 | 0 | 0 |
| `-s` | `filter_units=remove_types=99` | 206 | 0 | 0 |
| `-s` | `h264_metadata` | 206 | 0 | 0 |
| Normal restored | Stream copy, no filter | 6 | 470 | 245 |
| Normal restored | `filter_units=remove_types=99` | 231 | 0 | 0 |
| Normal restored | `h264_metadata` | 231 | 0 | 0 |

All six filtered comparison outputs had zero decoder diagnostic lines.

## Direct RTP capture, independent of FFmpeg

A small Python socket client issued DESCRIBE, SETUP and PLAY for the video
track, using TCP interleaving. It retained the original `$` framing and RTP
packets locally. It did not use FFmpeg, request audio, or change the camera.
This is an application-level capture of original RTP packet bytes, not a
network-interface PCAP. Raw captures contain private video and are excluded
from this repository.

| Observation | Normal grabber | Grabber with `-s` |
|---|---:|---:|
| Capture duration | 15.04 s | 15.01 s |
| RTP packets | 1,624 | 1,649 |
| RTP sequence discontinuities | 0 | 0 |
| Payload format | All FU-A (type 28) | All FU-A (type 28) |
| Complete reconstructed units | 298 | 300 |
| Reconstructed NAL header type | 0 in all units | 0 in all units |
| Units containing Annex-B start codes | 298 | 300 |
| SEI units found by parsing embedded Annex-B | 305 | 0 |

For example, a starting FU-A packet has indicator `1c`, FU header `80`, and
fragment data beginning `00 00 01 41 ...`. Reassembling the advertised NAL
produces `00 00 00 01 41 ...`, i.e. an Annex-B start code where the NAL header
should be. With the normal grabber, an example reconstructed unit is 5,469
bytes and contains a second start code at offset 5,418 introducing type 6.
The normal capture includes non-IDR/SEI groups and SPS/PPS/IDR/SEI groups.

Header bytes and sequence continuity were checked separately from the
reconstruction code. The normal capture ends with one unfinished FU group;
the counts above exclude that final partial unit.

[RFC 6184 section 5.8](https://www.rfc-editor.org/rfc/rfc6184#section-5.8)
defines fragmentation of a single NAL unit, with its original NAL type in
the FU header. The observed type-0 header and embedded Annex-B framing are
already present on the wire, so they are not introduced by FFmpeg's RTSP
depayloader. This narrows the defect to the camera-side packetization path.

Skipping SEI removes the additional SEI units but leaves type-0 FU headers
and embedded start codes. The successful MP4 test therefore does not prove
that `-s` repairs all packetization defects, or that the SEI payloads themselves
are malformed. The earlier no-op-filter result remains valid; it simply did
not rule out an SEI-related interaction before downstream reserialization.

## Source lead, not a verified binary-level fix

The local firmware source checkout pins RtspServer revision
`3c642bc9e5de0473cd9a0ad0fd459dfc4b16cdeb`. At that revision,
[`VideoFile::ReadFrameH264`](https://github.com/roleoroleo/RtspServer/blob/3c642bc9e5de0473cd9a0ad0fd459dfc4b16cdeb/example/other/VideoFile.cpp)
copies a span starting at an Annex-B prefix. The video sender forwards that
span, while
[`H264Source::HandleFrame`](https://github.com/roleoroleo/RtspServer/blob/3c642bc9e5de0473cd9a0ad0fd459dfc4b16cdeb/src/xop/H264Source.cpp)
derives the FU NAL type from the first byte. This is consistent with the wire
evidence. The installed 0.5.7 binary has not been mapped to an exact source
commit, so this is a review target rather than proof of its precise build.
An upstream repair should review NAL splitting, start-code removal and RTP
marker/timestamp behavior, not merely remove one SEI type.

## Operational impact and recovery

The experiment used a temporary copy of the camera service script and a
camera-side four-minute rollback timer. The persistent service script's
SHA-256 was unchanged before/after the successful test. Its normal grabber
command was restored without `-s`.

The first attempt failed to launch RTSP because SSH lacked the normal boot
`LD_LIBRARY_PATH`. Recovery explicitly supplied the firmware library paths.
This caused an indexed recording gap of 68.6 seconds beginning 07:14:41 UTC.
The corrected attempt produced the table above.

After the restored-baseline capture, a recent production segment had one
macroblock decode error, then the pilot camera rebooted without an explicit
reboot command. Its indexed gap was 53.5 seconds beginning 07:19:40 UTC.
The cause was not isolated; diagnostic load/restarts cannot be excluded.
This is an additional reason not to deploy `-s` fleet-wide from this trial.
The camera returned with its normal settings and key-based SSH access.

Final checks: one recent completed recording per camera decoded with no
errors (H.264 plus AAC, ages 22–30 seconds). The independent VPS gateway
checker passed for all six cameras, with recording ages 6–15 seconds.
The pilot's speaker key restriction, disabled password authentication and
idle speaker FIFO were reverified after reboot. These are point-in-time
recovery checks, not a long stability soak or an audible intercom retest.

## Separate cam4/cam5 reliability investigation

A six-hour recording-index review found 20 cam4 gaps over 20 seconds, totaling
2,943.9 seconds (about 49 minutes), ranging from 86.9 to 296.2 seconds. Cam5
had one 58.1-second gap. These predated the cam2 test. Index gaps describe
missing indexed coverage, not a complete corruption inventory.

The retained Frigate log before testing covered approximately 08:00–09:44
Riyadh time on September 19: cam4 had 56 no-frame watchdog events and cam5
had two. These are retries/events, not 58 distinct outages. The logs also
contain decoder errors and timestamp discontinuities, but no issue-593
`Invalid NAL unit size` / split-NAL signatures with the production workaround.

Both cameras had over three days of uptime, excluding full camera reboots
as the cause of these sampled gaps. Cam5's kernel log contains a
`cfg80211_connect` warning, without
enough timing evidence to associate it with the recording gap. Network drop
counters alone do not establish Wi-Fi as the cause.

There is insufficient evidence to link these outages to issue 593 or claim
them fixed. The next useful observation is a simultaneous camera process,
reachability and frame-flow snapshot during a cam4 outage. Unconditionally
rebooting cameras or changing firmware would obscure that evidence.
