# Live-audio rollout: all four MStar cameras — 2026-09-12

Completes the staged rollout of the go2rtc live-listening pilot in
`docs/live-audio-pilot.md` across every MStar camera. No firmware was changed
and no recording input was touched.

| camera | live audio | notes |
|---|---|---|
| cam5_laundry | yes | original pilot, audible sound confirmed by owner |
| cam2_living | yes | added first, strongest signal of the four |
| cam1_mensroom | yes | added at owner's direction; wedge-prone |
| cam4_hallway | yes | added at owner's direction; wedge-prone |
| cam3_kitchen | **no** | Allwinner, no audio track exists at source |
| cam6_extra | **no** | Allwinner, no audio track exists at source |

## Handoff step 2: every camera was measured, not assumed

The handoff said not to assume cam5's `asetpts` correction transfers. It does -
all four MStar cameras are identical, `pcm_s16be` 8000 Hz mono with the audio
clock running at half real time:

| camera | codec | rate | requested | decoded | ratio | RMS dBFS |
|---|---|---|---|---|---|---|
| cam1_mensroom | pcm_s16be | 8000 | 10 s | 19.993 s | 2.00 | -47.61 |
| cam2_living | pcm_s16be | 8000 | 10 s | 19.878 s | 1.99 | -35.13 |
| cam4_hallway | pcm_s16be | 8000 | 10 s | 19.977 s | 2.00 | -51.30 |
| cam5_laundry | pcm_s16be | 8000 | 10 s | 19.974 s | 2.00 | -46.07 |

### A measurement trap worth recording

The discriminating ratio is **decoded / requested**, not wall / decoded.

`-t N` limits by the *stream's own* timestamps. On a camera whose audio clock
advances at half real time, asking for 10 seconds of stream time runs 20 real
seconds and yields 20 seconds of real samples:

```
decoded/requested = 2.00   <- correct signal, fault obvious
wall/decoded      = 1.01   <- looks perfectly healthy, hides it completely
```

The first version of `scripts/probe-camera-audio.py` used wall/decoded and
reported cam2 as **not needing** the correction. It needed it. The heuristic
was wrong, not the camera.

## Guard against a silent misconfiguration

Before each restart, both invariants are checked: every `go2rtc.streams` key
matches a real Frigate camera key, **and** each stream's RTSP IP matches that
same camera's own recording input. A stream pointed at the wrong camera would
otherwise work perfectly and show the wrong room.

```
cam1_mensroom  go2rtc=192.168.3.5     camera_input=192.168.3.5     MATCH
cam2_living    go2rtc=192.168.3.22    camera_input=192.168.3.22    MATCH
cam4_hallway   go2rtc=192.168.3.4     camera_input=192.168.3.4     MATCH
cam5_laundry   go2rtc=192.168.3.149   camera_input=192.168.3.149   MATCH
```

## Verification

`scripts/verify-live-audio-any.py` generalises the pilot's cam5-specific script
to take a stream name and dimensions. `scripts/verify-all-live-audio.sh` reads
the stream list from the *live* config so it cannot drift from what is deployed.

Representative passing sweep:

```
cam1_mensroom   PASS   video_frames=182   aac_rms=-52.24   opus_rms=-50.29
cam2_living     PASS   video_frames=175   aac_rms=-43.29   opus_rms=-39.23
cam4_hallway    PASS   video_frames=162   aac_rms=-46.34   opus_rms=-42.99
cam5_laundry    PASS   video_frames=166   aac_rms=-40.47   opus_rms=-37.19
```

### Recording and detection are unaffected

Sampled repeatedly while all four live-audio streams were being exercised:
all six cameras held **5.0-5.1 fps**, `STATUS: ALL OK`, detector 11.27 ms, and
every camera's newest recording still decoded at full resolution. Caveat: the
samples returned identical figures, consistent with a steady stream but not
proof that Frigate is not averaging its own statistics.

## Open item reproduced: intermittent audio failure under load

The pilot documented an unresolved intermittent startup/reconnect failure
(an Opus `DESCRIBE 404`). It reproduces, and this rollout extends it to all
four cameras. It did not introduce it.

| test | result |
|---|---|
| sweep 1 | cam4 FAIL |
| sweep 2 | all PASS |
| sweep 3 | cam4 FAIL |
| cam4 alone, 5 consecutive runs | **5 / 5 PASS** |
| sweep 4 | cam1 FAIL |
| sweep 5 | all PASS |

Roughly **3 failures in 20 stream-tests during sweeps, and 0 in 5 isolated
runs**. Two readings of this are worth separating:

- It is **not camera-specific.** An earlier draft of this document claimed the
  failure was always cam4; sweep 4 then failed on cam1. The failure rotates.
- It appears only when several streams are opened in rapid succession. Each
  verification opens three connections (fragmented MP4, AAC RTSP, Opus RTSP),
  each of which makes go2rtc open another connection to the camera. Testing all
  four back to back is a much harsher pattern than one person watching one
  camera, so day-to-day impact is expected to be low - but a reconnect may
  occasionally come up without audio and need a refresh.

The failing runs could not be caught with their diagnostic output attached;
every sweep run with full capture happened to pass. The specific error text in
the pilot doc (`DESCRIBE 404` after 5.03 s) remains the best evidence.

## Upstream #588 assessment — no impact on this setup

`roleoroleo/yi-hack-MStar#588`, "y203c no aac audio on 0.5.7", closed
2026-04-27. AAC **output** was broken on 0.5.7 and was fixed by commit
`fc960adf`, titled *"Restore old rRTSPServer version"* - a wholesale revert
(`rRTSPServer.cpp +122/-869`). It is **not in any release**: 0.5.7 remains the
latest and `compare 0.5.7...fc960adf` reports `ahead_by: 2`. The only artifact
is a prebuilt `rRTSPServer` binary the maintainer attached to the issue
(ARM 32-bit ELF, 941 KB unpacked, sha256
`53925d9d4e21b3a580a0574ba533b99f4ac538563e4f6e669d2b7d475362324b`).

It does not affect anything here:

1. #588 is a bug in **`rRTSPServer`**. All four MStar cameras run
   **`rtsp_server_yi`** (`RTSP_ALT: alternative`).
2. The cameras emit **`pcm_s16be` (L16) 8000 Hz**, measured on all four - not
   AAC. There is no AAC codec selector in their `system.conf` at all; the only
   fields are `RTSP_AUDIO: yes`, `RTSP_AUDIO_NR_LEVEL`, `SPEAKER_AUDIO` and
   `ONVIF_AUDIO_BC`.
3. The AAC in this pilot is produced by **ffmpeg on the NVR**, not by the
   camera, so a camera-side AAC bug cannot reach it.

**Where it will matter.** `rRTSPServer` is the only daemon that advertises the
ONVIF audio backchannel, so any attempt at two-way audio - the pilot's next
stage - means switching to it, and then the #588 fix becomes required. There is
a possible bonus: the ~100 s stall that drove the original move to
`rtsp_server_yi` was measured on 0.5.7's **new** rRTSPServer, and the #588 fix
restores the **old** implementation. Two further commits
(`Improve WAVAudioFifoSource`, `Improve rRTSPServer reliability`, both touching
the `_BC` backchannel files) land on top. So a future release may allow stable
streaming *and* two-way audio *and* clean recordings together. All of it is
unreleased, and installing it needs SSH enabled - currently `SSHD: no`,
`TELNETD: no`, `FTPD: no`, with only ports 80 and 554 open.

Note also that #558 is a different, unrelated issue ("Identify Temu YI
camera", closed 2025-08-13).

## What is still NOT established

- **Audible sound is confirmed for cam5 only.** Nonzero RMS proves signal, not
  intelligibility. cam1, cam2 and cam4 need a human to open them and listen.
- Wall time includes connection and probing; it is **not** end-to-end latency.
- No off-LAN listening test from a phone on the tailnet.
- Browser transport was never identified; Frigate may fall back to video-only
  jsmpeg, which has no audio.
- No speaker audio has been sent. This is listening only.

## Operational notes

`docker restart frigate` does **not** re-evaluate the compose startup
dependency, so the tailnet drops and the Tailscale sidecar must be restarted
explicitly afterwards, with tailnet access then verified. This matches the
pilot doc's warning.

cam1 wedged during this rollout and was rebooted; cam1 has now wedged three
times and cam4 twice in the last fortnight. A wedged camera takes its live
audio down with it. That is a pre-existing fault, unrelated to this change.

## Rollback

Remove the relevant stanza(s) from `go2rtc.streams`, restart Frigate, restart
the Tailscale sidecar, and verify tailnet access. Recording inputs and camera
firmware were never modified.
