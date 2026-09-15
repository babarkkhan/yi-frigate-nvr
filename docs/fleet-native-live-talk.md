# Native Frigate intercom rollout

The owner requested extending the working cam1 pilot to all six cameras, with
audible checks deferred until someone can listen near the cameras. The existing
Google account allowlist and website media relay are reused. There is no new UI.

## Camera-specific credentials

`speaker_bridge.py` accepts a fixed camera identifier, `cam1` through `cam6`.
Omitting it retains the original cam1 behavior. The private credential paths are:

| Camera | Hardware | Private credential directory |
|---|---|---|
| cam1, men's room | MStar | `/config/.live-talk/` (original pilot) |
| cam2, living room | MStar | `/config/.live-talk/cam2/` |
| cam3, kitchen | Allwinner | `/config/.live-talk/cam3/` |
| cam4, hallway | MStar | `/config/.live-talk/cam4/` |
| cam5, laundry | MStar | `/config/.live-talk/cam5/` |
| cam6, extra | Allwinner | `/config/.live-talk/cam6/` |

Each directory contains `bridge.json`, `known_hosts`, and a distinct
`speaker_key`. Shared Python dependencies stay in `/config/.live-talk/vendor`.
Recovery keys and complete before-state backups belong in the private host's
ignored `secrets/` directory, outside Frigate's configuration mount.

Both the full-resolution and Data saver source for each camera append its own
backchannel. For example, both kitchen streams use:

```yaml
- "exec:python3 /config/live-talk/speaker_bridge.py cam3#backchannel=1#audio=alaw/8000"
```

The original cam1 source remains valid without an argument. Unknown camera IDs
and path-like arguments are rejected. The camera selector changes credentials,
not the audio format: all bridges convert PCMA/8000 into mono S16LE/16000.
Allwinner 0.4.0's own speaker page specifies that same playback format. Audible
confirmation on that hardware must still come from a listener.

## Provisioning and recovery

Provision one camera at a time. Save its complete settings before enabling SSH
with a random bootstrap password. After reboot, verify the speaker FIFO and
writable startup file, generate distinct speaker/recovery keys, and save the
recovery bundle outside Frigate before installing anything on the camera.

Use the same forced-command script as the cam1 pilot. Restrict the speaker key
to that script, reject arbitrary commands, disable forwarding/PTY access, and
check the source IP observed in the actual SSH connection. Account home paths
may include a trailing slash; normalize it when checking the directory.

MStar's original listener is `dropbear -R`. The inspected Allwinner startup
uses `dropbear -R -B -p 0.0.0.0:22`. Preserve its explicit listener address,
remove the blank-password allowance, and add `-s` to disable password login.
Do not copy one model's complete startup script onto another. Preserve all
unrelated startup logic and existing authorized keys.

Reboot again after installing the key-only startup configuration. Confirm the
speaker key still works, arbitrary commands still fail, password authentication
is rejected, and the recording process recovers. Preserve camera RTSP and audio
settings exactly, including cam5's existing `ONVIF_AUDIO_BC=G711` and cam6's
existing `RTSP_STREAM=both`.

If provisioning fails, restore the saved camera files when accessible and its
original SSH settings, then reboot it before continuing. Retain failed-attempt
backups for diagnosis. The cam2 readiness check initially rejected a harmless
trailing slash; those attempts were rolled back before the check was corrected.

For rollback of an individual deployed camera, first remove its full/mobile
backchannel entries and restart go2rtc. Restore its startup and authorized keys
from the private recovery bundle, restore the previous SSH settings and reboot.
Other cameras and the shared gateway can remain enabled. Do not remove the
instance-wide exec opt-in or shared dependencies while other bridges need them.

## Validation and limits

All five new camera installations survived a second reboot with key-only SSH
and working restricted speaker commands. Password login was rejected, arbitrary
commands were rejected, and the speaker FIFO was idle after each test. Recovery
bundles were saved outside Frigate before camera files were changed.

Each new bridge delivered one second of digital silence as 31,998 PCM bytes and
exited successfully; the resampler's first-sample boundary accounts for the
two-byte difference from 32,000. The camera speaker lock was released afterward.
Configuration checks verified all twelve full/mobile backchannels against the
intended six camera hosts, six distinct speaker keys, and unchanged recording
and relay settings. Four offline audio, error-handling and camera-selector tests
passed.

Browser tests then passed for all twelve full-resolution/Data saver streams:
video decoded at 1920/960 pixels wide, listening audio arrived, and synthetic
silent PCMA microphone audio was sent through the VPS TCP relay. Backend
speaker-sender packet counters were also checked for each camera on its full
stream. These short tests reported no inbound packet loss. Transport round-trip
times ranged approximately 0.23–0.66 seconds; this is not mouth-to-ear latency.
Fresh completed recordings from all six cameras decoded without errors after
the camera rollout.

The independent VPS checker initially timed out when it issued six recording-
history requests at once. A single local history request took about three
seconds; sequential VPS requests then passed for every camera with fresh
recordings. The checker now reads history sequentially without relaxing its
ten-second request timeout or 120-second freshness threshold. The underlying
history-query performance bottleneck has not been fully isolated.

Audible confirmation is already available for cam1 only. The owner explicitly
deferred listening checks for cam2–cam6. Automated silent audio tests can verify
transport and session cleanup, but cannot establish speaker loudness, echo,
normal speech speed or a useful conversation from the next room.

The two-minute bridge-process limit, single-caller-per-camera recommendation,
TCP media relay, private management requirement and instance-wide
`GO2RTC_ALLOW_ARBITRARY_EXEC` setting from the
[cam1 deployment notes](cam1-native-live-talk.md) continue to apply.

## WebRTC recovery after a live-service restart

Fleet validation caught a shared transport fault: after restarting go2rtc while
Tailscale was already running, browsers sent ICE requests to the VPS TCP
candidate but received no responses. The relay and SSH tunnel were healthy;
restarting the relay did not fix it. Camera recordings continued normally.

go2rtc 1.9.10 automatically excludes Docker-like addresses when another eligible
interface is present. With only Docker networking at startup it falls back to
using that address; with `tailscale0` already present, it excludes the Docker
address that receives the forwarded media connection. This made live-service
restarts behave differently from the original cold container startup.

The small executable `/config/go2rtc` wrapper runs `prepare_webrtc.py`, which
resolves the current container IPv4 and adds it to the generated configuration's
`webrtc.filters.ips` before executing the unchanged, pinned go2rtc binary.
This is resolved at every start rather than hardcoding a Docker address.
The public VPS candidate, hidden automatic candidates and TCP-only policy are
preserved. Two offline tests cover address refresh/settings preservation and
rejection of invalid/loopback/multicast addresses.

Install the wrapper with LF endings and execute permission (`chmod 755`).
Frigate's supported custom-go2rtc entry point detects `/config/go2rtc`; this
wrapper still executes `/usr/local/go2rtc/bin/go2rtc` from the pinned image.
Remove the wrapper to return to stock startup, but that also restores the
observed restart fault while this network layout and go2rtc version remain.

Source: [go2rtc 1.9.10 interface and IP filtering](https://github.com/AlexxIT/go2rtc/blob/v1.9.10/pkg/webrtc/api.go).
