# Cam1 native Frigate live-talk pilot

> **Fleet extension:** the owner subsequently authorized all six cameras. See
> [the rollout notes](fleet-native-live-talk.md) for per-camera credentials and
> validation. The rest of this document records the original cam1 pilot.

This pilot uses the microphone toggle inside Frigate 0.17.2, on the men's room
camera only. Both approved Google accounts may use it. The separate
record-and-send page and service were removed at the owner's request.

Open the HTTPS camera website, refresh, open the men's room camera, and tap the
microphone. Allow browser microphone access, speak, then tap again to stop.
Frigate's existing control is a toggle, not a hold-to-record button. Listening
and video remain in the same player. Full resolution and Data saver both have
the speaker backchannel. Other cameras remain listening-only.

## What has been verified

- The owner heard a 2.63-second phrase streamed through the new bridge clearly,
  at normal speed. Audio was delivered in 20 ms chunks, without a clip upload.
- An isolated WebRTC test using Frigate's transceiver pattern negotiated
  PCMA/8000 and delivered 40,000 audio bytes in five seconds.
- A browser receive-only test selected the VPS TCP candidate: audio arrived,
  49 video frames decoded at 960 pixels wide, and no packet loss was reported
  in that short test. Measured transport round-trip time was 253 ms; this is
  not a measurement of mouth-to-ear delay.
- Frigate's metadata exposes `audio, sendonly, PCMA/8000`, which enables its
  native microphone control. The owner then confirmed a real phone call works
  in both directions, with slight echo while in the same room as the camera.
  An acoustically separated call and cellular performance remain untested.
- An isolated copy of the deployed Caddy rules rejected anonymous/forged
  identities and other viewers for WebRTC, allowed both approved accounts,
  retained their viewer roles, and denied the admin users endpoint.
- All six latest completed recordings decoded successfully after deployment.
- After the phone test the camera speaker lock was absent (idle), and only the
  speaker key remained in Frigate; recovery credentials were kept outside it.
- Three offline tests passed: chunked conversion preserves samples/duration,
  connection failures do not transmit/retry/leak error details, and camera
  rejection closes the session and reports failure.

## Audio path

Browser microphone → WebRTC PCMA/8000 → go2rtc exec backchannel → streaming
A-law decode/resample → pinned-host-key SSH → camera `/tmp/audio_in_fifo`.
The camera FIFO expects mono signed 16-bit little-endian PCM at 16 kHz.

The existing stable alternative RTSP daemon and recording inputs are unchanged.
There is no new firmware binary or public camera CGI. `speaker_bridge.py`
converts chunks as they arrive; it never assembles a spoken message or retries
a failed delivery. Each bridge process has a two-minute lifetime limit. This
is not a Frigate UI timer; toggle the microphone off when finished. Use one
caller at a time during the pilot. The camera lock prevents separate bridge
processes from simultaneously owning its FIFO, but does not implement a
browser-user queue or arbitration inside a shared go2rtc stream.

## Deployment and credentials

The committed configuration is a template, not a turnkey public deployment.
Replace the documentation-only VPS address and account patterns before use.

1. Preserve camera settings, startup script, authorized keys and SSH host key.
   Cam1 required enabling SSH and a brief reboot. Do not repeat this on other
   cameras without a separate pilot.
2. On this MStar camera, root's writable home is `/home/yi-hack`. Install the
   reviewed `camera-speaker.sh` there under `script/frigate-speaker.sh`, mode
   700, with the actual NVR source IP. Install a dedicated RSA speaker key with
   `command="/home/yi-hack/script/frigate-speaker.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty`.
   This Dropbear build rejected `from=` key restrictions, so the forced command
   checks `SSH_CONNECTION`. Arbitrary commands returned exit 126 in testing.
3. Keep a distinct recovery key and rollback bundle outside Frigate. Restrict
   `.ssh`/authorized_keys to 700/600. Start Dropbear with `-s` and persist that
   flag in its existing startup script. Password login was tested and rejected;
   a second camera reboot to verify persistence has not yet been performed.
   Firmware upgrades may overwrite this startup/script customization.
4. In the private, Git-ignored `/config/.live-talk/` directory provide only
   `speaker_key`, pinned `known_hosts`, and `bridge.json`, for example
   `{"host":"192.0.2.20","max_seconds":120}`. No passwords, keys, host-key
   bundles, or recovery credentials belong in public Git. Remove temporary
   bootstrap/recovery credentials from the container after external backup.
5. Install `live-talk/requirements.txt` into `/config/.live-talk/vendor` with
   `pip --no-deps --target`. The pinned image supplies Python 3.11/audioop and
   cryptography 44.0.3. Do not upgrade global Python dependencies. Validate this
   assumption before changing Frigate's image; audioop is absent in Python 3.13.
6. The owner explicitly approved `GO2RTC_ALLOW_ARBITRARY_EXEC=true`. This is an
   instance-wide opt-in, not a cam1 sandbox. Trust all stream configuration and
   retain private management access. Public users stay viewers. Ports 5000,
   1984, and 8554 must not be forwarded from the Internet.

## Website media relay

The existing SSH tunnel still carries the authenticated Frigate HTTP connection
through VPS loopback 18971. It now also forwards VPS loopback 18555 to home
8555. Update both SSH `PermitListen` and the dedicated tunnel key's
`permitlisten` options to permit exactly those two loopback listeners.

Install `home-nvr-webrtc.socket` and `.service` on the VPS. The socket listens
on public IPv4 TCP 8555 and systemd-socket-proxyd relays it to loopback 18555.
Allow TCP 8555 in the VPS firewall. No go2rtc HTTP API is exposed by this port.
WebRTC carries encrypted DTLS/SRTP and obtains session credentials through
Google-authenticated signalling. Caddy limits `/live/webrtc/*`, `/live/mse/*`,
`/api/go2rtc/api*` and `/api/go2rtc/webrtc*` to the two approved identities after
discarding client-supplied identity headers. MSE and WebRTC aliases share an
upstream WebSocket handler, so guarding only the WebRTC-named route is not
sufficient. Other authenticated identities cannot use those live signalling
paths; this is not a permission system that distinguishes listening from talking.

go2rtc advertises only the VPS TCP candidate. Thus WebRTC uses the VPS even on
home Wi-Fi; MSE's existing HTTPS path is unchanged. Packet loss may make TCP
less responsive than a future UDP/TURN path. This is a pilot tradeoff, not a
claim of lowest possible latency. The public port still permits unsolicited
connection attempts; its bounded proxy connections are not a DDoS defense.

## GPU recovery discovered during deployment

After service-unit reloads and the camera reboot, new GPU processes could no
longer initialize CUDA inside Frigate. Cam1 stopped recording while the other
five existing processes continued. Mobile live encoders also failed to start.
Windows and WSL still saw the GPU; the container reported GPU access blocked.
This is consistent with NVIDIA's documented systemd/cgroup reload issue.

Recreating Frigate restored GPU access. Compose now explicitly includes the
WSL `/dev/dxg` device, NVIDIA's documented class of mitigation, while keeping
the pinned image. Its Tailscale companion was recreated to follow the new
network namespace. This caused a brief fleet recording interruption; cam1's
earlier outage was longer. Fresh segments from all six cameras then decoded.
The mitigation has not yet had a deliberate daemon-reload stress test. Remove
the WSL-only device mapping when adapting this configuration to native Linux.

## Rollback

Remove the two cam1 exec source lines and the custom-command environment
opt-in. Restore the prior go2rtc WebRTC settings if retiring the relay. Restart
go2rtc to reload streams; environment changes persist through Compose on the
next container recreation. Frigate regenerates `/dev/shm/go2rtc.yaml` on each
go2rtc restart, so editing that temporary file alone is not a deployment.

Stop/disable the VPS WebRTC socket and its active proxy service, close public
TCP 8555, and remove the 18555 reverse forward and both SSH permission entries.
Retain the existing 18971 Google gateway. Restore the camera startup/settings
and authorized keys using the private recovery bundle, then disable camera SSH
if retiring the bridge. Do not restore the rejected record-and-send page.

## Sources

- [Frigate exec-source opt-in](https://docs.frigate.video/configuration/restream/#security-restricted-stream-sources)
- [Frigate 0.17.2 native live controls](https://github.com/blakeblackshear/frigate/blob/v0.17.2/web/src/views/live/LiveCameraView.tsx)
- [go2rtc 1.9.10 exec backchannel](https://github.com/AlexxIT/go2rtc/blob/v1.9.10/internal/exec/README.md)
- [NVIDIA GPU-access loss and mitigations](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/troubleshooting.html)
