# Cam1 speaker pilot and intermittent audio controls

> **Update:** the owner selected live intercom inside Frigate and rejected the
> separate record-and-send page, which has been removed. See the
> [native live-talk pilot](cam1-native-live-talk.md) for the current implementation.
> The clip test and options below are the earlier investigation.

The owner confirmed that phone playback and ongoing latency are acceptable.
The remaining listening issue is an intermittent missing speaker control inside
a single camera's live view. Cam1 was selected for the speaker pilot.

## Cam1 can play spoken clips

Cam1 is MStar/y203c, yi-hack 0.5.7. Its existing settings were:
`RTSP_ALT=alternative`, `RTSP_STREAM=high`, `RTSP_AUDIO=yes`,
`SPEAKER_AUDIO=yes`, `ONVIF_AUDIO_BC=NONE`.

With an observer ready, one "Camera one speaker test" clip was sent as:

- Headerless signed 16-bit little-endian PCM, 16 kHz, mono.
- 84,294 PCM bytes, approximately 2.63 seconds.
- Multipart form field `file`, filename `test.pcm`, content type
  `application/octet-stream`; the Content-Type part header came last.
- `POST /cgi-bin/speaker.sh?voldb=0`, with no gain boost.

The camera returned HTTP 200 / `error: false` after 4.22 seconds. **The owner
confirmed hearing the words clearly.** No camera configuration, firmware,
RTSP daemon, or recording settings were changed for playback.

This disproves the old blanket claim that speaker uploads need an active RTSP
backchannel. The tested path is independent of the missing standard RTSP talk
track. Only cam1 has an audible speaker confirmation from this pilot.

The older `camera-speak.ps1` used 8 kHz/raw HTTP upload. It now uses the tested
16 kHz/multipart format, checks conversion failures and camera rejection, caps
clips at ten seconds, defaults to unity gain, and cleans temporary files on
failure. `-RawPcm` accepts already-converted headerless PCM; `-PrepareOnly`
validates without transmitting. Offline tests cover binary multipart framing,
dry-run behavior, malformed/oversized PCM, and camera rejection.

This is **spoken clip playback**, not continuous live push-to-talk. The current
CGI collects the upload before playing it; it is not a continuous audio socket.
The next implementation decision is either:

1. Hold to record, release to send: a phone recorder and authenticated,
   size-limited cam1 upload service using this proven path. Serialize uploads
   per camera: the firmware uses a fixed temporary filename. Require browser
   origin/CSRF checks and explicit talk authorization, not an exposed CGI proxy.
2. Live push-to-talk while the user speaks: further camera-side streaming
   development or a proven RTSP backchannel implementation. The stable daemon
   currently advertises no speaker track. The standard Frigate talk button
   cannot be enabled by simply pointing it at the clip-upload CGI.

Keep any next pilot limited to cam1. HTTPS already exists for microphone
permission, but a transport and application authorization are still required.
Do not expose the camera CGI publicly or switch the recording fleet to the
previously unstable RTSP daemon.

## Why the speaker control can disappear

Frigate 0.17.2 hides the control if its player falls back to jsmpeg, which has no
audio. It also hides it when stream metadata reports no audio. In the measured
opens, metadata correctly reported H.264 plus AAC and Opus, but MSE startup was
slower than the default fallback timeout:

| Stream | MSE response after opening WebSocket |
|---|---:|
| cam1 Data saver, first open | 5.816 seconds |
| cam5 Data saver | 6.855 seconds |
| cam1 Data saver, repeat | 4.993 seconds |

The player defaults to **3 seconds**. This reproduces a concrete timeout
condition that can cause the reported behavior; the actual phone's console was
not captured, so it is not proof that every disappearing icon has this cause.

Use Frigate's built-in **Settings → General → Live Player Fallback Timeout** and
set it to **10 seconds** on each phone/browser, then reopen the camera. This is
stored in IndexedDB per username and origin, not in server YAML or the user API.
It must also be set for another user's browser. It changes how long the player
waits before falling back, not normal audio/video latency. A genuine failed
stream will take longer to fall back. Phone confirmation after the change is
still pending.

When already in the video-only fallback, camera stream information offers
**Reset stream**; closing and reopening the camera also retries. Our named
**Data saver** stream supports audio and is distinct from Frigate's jsmpeg
fallback.

Two isolated alternatives were rejected and not deployed: aggressive FFmpeg
probing lost video headers or timed out, and a metadata preflight before the
WebSocket did not keep all six streams warm reliably. The original production
camera inputs, gateway route, and recording pipeline were preserved.

## Source references

- [MSE player and liveFallbackTimeout](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/components/player/MsePlayer.tsx)
- [General settings preference](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/views/settings/UiSettingsView.tsx)
- [Speaker-control visibility and fallback](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/views/live/LiveCameraView.tsx)
- [Per-user browser persistence](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/hooks/use-user-persistence.ts)
- [MStar speaker CGI](https://github.com/roleoroleo/yi-hack-MStar/blob/0.5.7/src/www/httpd/cgi-bin/speaker.sh)
