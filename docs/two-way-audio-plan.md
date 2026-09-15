# Two-way audio: historical RTSP investigation

> **Current pilot:** cam1 now has a streaming SSH speaker bridge exposed through
> Frigate's native microphone control. The owner confirmed both the streamed
> phrase and a phone call in both directions, with slight same-room echo. See
> [native live-talk deployment and evidence](cam1-native-live-talk.md).
> The findings below predate this bridge and do not describe the current setup.

> **Latest:** the owner clearly heard a 16 kHz multipart spoken upload on cam1,
> with the stable alternative daemon and `ONVIF_AUDIO_BC=NONE`. The separate
> speaker-upload path works on cam1. See [the pilot and next implementation
> choices](cam1-talk-pilot-and-audio-controls.md). The sections below are historical
> findings and do not describe the current go2rtc configuration.

> **Follow-up 2026-09-12:** the measured missing RTSP backchannel remains a
> blocker for the standard talk path. The broader conclusion about speaker
> uploads is being revisited: the 0.5.7 playback page specifies 16 kHz (the old
> test used 8 kHz), the upload parser can misread raw PCM, and the audio library
> has a separate speaker FIFO reader. The owner confirmed live listening on cam5;
> audible speaker output remains unverified. See [live-audio-pilot.md](live-audio-pilot.md).

**Historical outcome:** the standard RTSP talk path required giving up daemon
stability. The evidence below remains relevant to that path; it does not rule
out the separate speaker-upload path described in the follow-up above.

## The finding

yi-hack ships two working RTSP daemons. Exactly one has the audio backchannel,
and it is the one that stalls.

| Daemon | Stability | Backchannel (two-way audio) |
|---|---|---|
| `rRTSPServer` (`RTSP_ALT: standard`) | **stalls** - froze at 100s, see camera-dropouts.md | **YES** |
| `rtsp_server_yi` (`RTSP_ALT: alternative`) | **rock solid** - 20+ min, zero failures | **NO** |

### Evidence - SDP from each daemon

`rtsp_server_yi`, with `ONVIF_AUDIO_BC: G711` set and `-b ulaw` on its command
line. Two tracks, no backchannel:

    m=video 0 RTP/AVP 96      a=control:track0
    m=audio 0 RTP/AVP 97      a=rtpmap:97 L16/8000   <- the mic
                              a=control:track1

`rRTSPServer`, same camera, same config. Three tracks - note `a=sendonly`:

    m=video 0 RTP/AVP 96      a=control:track1
    m=audio 0 RTP/AVP 0       a=control:track2       <- the mic
    m=audio 0 RTP/AVP 0       b=AS:8
                              a=sendonly             <- THE BACKCHANNEL
                              a=control:track3

The `-b ulaw` flag is accepted by `rtsp_server_yi` without complaint but it
simply does not advertise the track.

## What else was verified

- `SPEAKER_AUDIO: yes` and `ONVIF_AUDIO_BC: G711` set fine on all platforms
- `/tmp/audio_in_fifo` exists on the camera; a write to it completes, so
  something drains it
- `speaker.sh` accepts correctly formatted audio and returns `error: false`
- Audio format per upstream wiki: **8 kHz, 16-bit, mono, S16LE** - confirmed
- ONVIF config on the camera reports `audio_decoder=G711`
- **But no sound was ever produced.** Measured with a 1 kHz tone and a
  bandpass analysis of the camera's own mic feed:

      control (no tone) : -63.3 dB in the 1 kHz band
      little-endian PCM : -63.5 dB
      big-endian PCM    : -63.1 dB
      after enabling the backchannel : -63.9 / -64.0 / -64.3 dB

  No signal, under any combination.

Caveat on that measurement: these cameras almost certainly run acoustic echo
cancellation, so the mic is *designed* not to hear its own speaker. The tone
may have played inaudibly to the test. **This could not be settled without a
human in the room**, which is why the check below is left for you.

- TTS (`speak.sh`) returns "TTS engine not found". `nanotts` installs to
  `/tmp/sd/...`, i.e. it needs an SD card, and the cameras run cardless.

## Current state - everything restored

- All six cameras on `rtsp_server_yi` (stable)
- go2rtc removed from the Frigate config again
- SSH re-disabled on cam5 after diagnosis; ports remain 80 + 554 only
- `ONVIF_AUDIO_BC: G711` left set on cam5 - harmless, and ready if this is
  revisited

## Your options

1. **Accept no two-way audio.** Current state. Nothing is at risk.
2. **Dedicate one camera to talk.** Put a single camera on `rRTSPServer`,
   accept that it stalls and drops out, and use it only for talking. Viable if
   there is one spot where talking matters more than recording.
3. **Raise it upstream.** `rtsp_server_yi` not honouring `-b` looks like a gap
   rather than a deliberate omission - the flag is passed to it by the
   project's own `service.sh`. Worth an issue on roleoroleo/yi-hack-MStar.
4. **The Yi app still works for talk** if paired - it uses the proprietary
   path, not RTSP, which is exactly why it was unaffected by all of this.

## One check to run when you are back

`scripts/camera-speak.ps1` is written, syntax-checked and ready:

    .\scripts\camera-speak.ps1 -Camera cam5 -File message.wav -Volume 8

Stand next to the laundry camera and run it. If you hear anything at all, then
the speaker path works and only the *live* backchannel is missing - which
changes option 1 into "canned announcements work, live talk does not", a much
better position. If there is silence, the feature is fully blocked as described.
