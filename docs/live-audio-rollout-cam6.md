# Live-audio rollout: cam6_extra — 2026-09-12

Completes live listening across **all six cameras**, following the gates in
`docs/live-audio-pilot-allwinner.md`. cam6 is the second Allwinner unit
(y20ga, yi-hack 0.4.0).

## Gates followed

**1. Baseline saved first.** cam6's complete system settings and status were
saved locally before any change (private, not in the public repo). Its stream
was confirmed video-only at baseline:

```
h264  video  1920x1080          <- no audio track
```

**2. Exactly one field changed**, verified by diffing the *complete*
before/after settings rather than spot-checking the field:

```
POST /cgi-bin/set_configs.sh?conf=system   {"RTSP_AUDIO":"pcm"}

26c26
< "RTSP_AUDIO":"yes"
---
> "RTSP_AUDIO":"pcm"
```

`RTSP_ALT=alternative` was left alone. The unstable `standard` daemon was not
touched, per the handoff.

**3. Rebooted, and the reboot confirmed.** Uptime went `63978s` -> `694s`.

This step is where care was needed. `reboot.sh` returned `error:false` but the
camera kept running for roughly a minute afterwards - a first uptime reading
taken immediately showed `64031s`, i.e. *higher* than before, and briefly
looked like the reboot had not happened. It had; it was simply delayed. A poll
loop waiting for the camera to "come back" also exited instantly because the
camera had not yet gone down. **Confirm a reboot by a uptime that has
decreased, not by the endpoint answering.**

**4. Source measured independently** rather than assuming cam3's result
transfers:

| camera | codec | rate | requested | decoded | ratio | clock | RMS dBFS |
|---|---|---|---|---|---|---|---|
| cam3_kitchen | pcm_s16be | 8000 | 10 s | 19.970 s | 2.00 | 0.50x | -57.82 |
| cam6_extra | pcm_s16be | 8000 | 10 s | 19.459 s | 1.95 | 0.51x | **-37.70** |

Same half-speed audio clock, so the same `-af asetpts=N/SR/TB` correction is
required. cam6's signal is markedly stronger than cam3's.

**5. Stream added and every mapping validated** before restarting - name,
RTSP IP against that camera's own recording input, and detect dimensions:

```
cam1_mensroom  192.168.3.5     MATCH  1920x1088
cam2_living    192.168.3.22    MATCH  1920x1088
cam3_kitchen   192.168.3.3     MATCH  1920x1080
cam4_hallway   192.168.3.4     MATCH  1920x1088
cam5_laundry   192.168.3.149   MATCH  1920x1088
cam6_extra     192.168.3.6     MATCH  1920x1080
```

## Verification

**cam6 alone: 5 / 5 PASS.**

The first individual run failed on Opus only - 4.1 s decoded with
`Error during demuxing: Connection timed out` - then five consecutive runs all
passed. That is the pre-existing intermittent reconnect fault, not a cam6
defect, and matches how cam4 behaved during the MStar rollout.

**System after the change**

```
all six cameras      5.0-5.1 fps, 0.0 skipped, STATUS: ALL OK
detector             7.7 ms
all six recordings   decode at full resolution, all fresh (<1 min)
tailnet              http://home-nvr:5000  HTTP 200  0.04 s
```

**Recordings now carry audio on every camera**, cam6 included - the PCM change
gives the Allwinner units a source track, and Frigate's existing record args
already transcode to AAC:

```
cam1_mensroom   h264,video   aac,audio,8000
cam2_living     h264,video   aac,audio,8000
cam3_kitchen    h264,video   aac,audio,8000
cam4_hallway    h264,video   aac,audio,8000
cam5_laundry    h264,video   aac,audio,8000
cam6_extra      h264,video   aac,audio,8000
```

Recording audio/video synchronisation has **not** been established.

## The intermittent fault scales with stream count

Six-stream sweep immediately after the rollout:

```
cam1_mensroom   FAIL   (opus)
cam2_living     PASS
cam3_kitchen    PASS
cam4_hallway    PASS
cam5_laundry    FAIL
cam6_extra      PASS
```

Failure rate by stream count during back-to-back sweeps, each stream passing
reliably in isolation:

| streams configured | typical sweep result |
|---|---|
| 4 | ~3 failures in 20 stream-tests |
| 5 | 2 of 5 failed |
| 6 | 2 of 6 failed |

It rotates between cameras, but **resource contention is not an established
cause**. These sequential sweeps did not control concurrent producer count or
capture every failure's diagnostic output. Each verification opens three
consumer connections (fragmented MP4, AAC RTSP, Opus RTSP); go2rtc may reuse a
producer or restart it after teardown. Configured streams are not necessarily
active camera connections. The underlying
intermittent startup/reconnect fault remains **unresolved**; this rollout
extends its blast radius to all six cameras without introducing it.

## Two bugs fixed in this project's own verification scripts

Both were failure-propagation faults - the exact class of error this project
keeps documenting elsewhere.

**1. `verify-all-live-audio.sh` reported success without checking anything.**
Caught in review of the cam3 pilot, and confirmed: if the stream list came back
empty - docker exec failing, unreadable YAML, a missing `go2rtc` block - the
loop body never ran, `rc` stayed 0, and it printed *"ALL STREAMS PASS"* and
exited 0. It now fails closed on an empty or unreadable list, on a stream with
no matching camera key, and on an unparseable result, and accepts an expected
stream count to assert against. Negative-tested: asking it to expect 99 streams
now exits 2 rather than passing.

**2. `repeat-live-audio.sh` hardcoded 1920x1088.** That is the MStar geometry.
Run against either Allwinner camera it would have reported false failures on a
perfectly healthy stream. It now reads dimensions from the live config.

## Divergence noted, deliberately not changed

cam6 has **`RTSP_STREAM=both`** where every other camera has `high`. Design
note 1 in the Frigate config warns against enabling both streams on these weak
SoCs, and cam6 carrying two streams is a plausible contributor to its load.
This is pre-existing and was left alone - changing it is a separate change
needing its own baseline and rollback.

## What is still NOT established

- **Audible sound from cam6 has not been confirmed by a human.** Nonzero RMS
  proves signal, not intelligibility. cam1, cam2, cam4 and cam6 all still need
  someone to open them and listen; only cam3 and cam5 are owner-confirmed.
- Wall time includes connection and probing; it is **not** end-to-end latency.
- Longer-term reconnect reliability, and the intermittent failure above.
- No off-LAN listening test from a phone on the tailnet.
- Recording audio/video sync.
- No speaker audio has been sent anywhere. This is listening only.

## Rollback

Remove the `cam6_extra` stanza from `go2rtc.streams`. Restore cam6's
`RTSP_AUDIO` to `yes`, verify the write by diffing the full settings, and
reboot the camera - confirming the reboot by a *decreased* uptime. Then restart
Frigate, restart the Tailscale sidecar, and verify actual tailnet access.
Recording arguments and camera firmware were never modified.
