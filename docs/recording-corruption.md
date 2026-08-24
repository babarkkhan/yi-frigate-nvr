# Recording playback failure - root cause and fix, 2026-08-24

Symptom, seen in the Frigate UI on cam4:

    Failed to play recordings (error 3):
    PipelineStatus::CHUNK_DEMUXER_ERROR_APPEND_FAILED:
    Failed to prepare video sample for decode

That is the browser's Media Source Extensions refusing the MP4.

## Root cause

**The MStar build of `rtsp_server_yi` emits malformed Access Unit Delimiter
(NAL type 9) and Filler Data (NAL type 12) units.**

They decode fine as a live stream, but they break the Annex-B to AVCC
conversion performed when muxing into MP4, producing zero-length NAL size
prefixes:

    Invalid NAL unit size (0 > 8246)
    missing picture in access unit with size 8312
    Error splitting the input into NAL units

Roughly 80 such errors per 20-second segment.

## How it was isolated

1. **Not audio.** The oldest cam4 segment also has an AAC track and has zero
   errors. Corruption begins at 2026-08-23 hour 04, two hours *before* AAC
   audio was re-enabled at hour 06.
2. **Not Frigate.** A plain `ffmpeg -c copy` from the camera to MP4 reproduces
   it exactly.
3. **Not the stream.** Decoding the live RTSP feed directly gives **0** errors.
   The corruption only appears once it is muxed into MP4.
4. **It is the daemon, and only on MStar.** Same camera, same 20-second pull:

    | Camera | Platform | Daemon | NAL errors |
    |---|---|---|---|
    | cam4 | MStar | `rRTSPServer` | **0** |
    | cam5 | MStar | `rtsp_server_yi` | **80** |
    | cam3 | Allwinner | `rtsp_server_yi` | 1 (just the mid-GOP join) |

   So the Allwinner build is fine; the MStar build is not.

## The trade-off this created

On MStar cameras, neither daemon was fully correct:

| | `rRTSPServer` | `rtsp_server_yi` |
|---|---|---|
| Streaming stability | **stalls at ~100s** | solid |
| MP4 recordings | clean | **corrupt** |
| Audio backchannel | yes | no |

Switching to `rtsp_server_yi` fixed the stalling and silently introduced the
recording corruption. Both were real; one just showed up later.

## Fix: strip the offending NAL types while muxing

Two options were tested, both giving 0 errors:

| Fix | Result | Cost |
|---|---|---|
| **`-bsf:v filter_units=remove_types=9\|12`** | 0 errors | none - no re-encode, and files are ~30% smaller |
| NVENC re-encode | 0 errors | GPU encode, quality loss, larger files |

The bitstream filter is strictly better and is what was applied. `record` in
`config.yml` is now an explicit arg list matching
`preset-record-generic-audio-aac` exactly, plus `-bsf:v`.

Verified after the change - every camera, freshly written segments:

    cam1 NAL-errors=0  tracks=h264,aac
    cam2 NAL-errors=0  tracks=h264,aac
    cam4 NAL-errors=0  tracks=h264,aac
    cam5 NAL-errors=0  tracks=h264,aac
    cam3 NAL-errors=0  tracks=h264
    cam6 NAL-errors=0  tracks=h264

## Note on existing footage

Segments recorded between 2026-08-23 04:00 and the fix are still corrupt and
will not play. They cannot be repaired in place - the damage is in what was
written. With 2-day retention they age out on their own.

## Worth reporting upstream

`rtsp_server_yi` on MStar producing NAL units that survive live decode but
break MP4 muxing is a genuine bug, and a second one in the same daemon after
the missing `-b` backchannel support. Both are worth an issue on
roleoroleo/yi-hack-MStar.
