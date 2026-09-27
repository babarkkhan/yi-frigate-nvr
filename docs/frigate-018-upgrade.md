# Frigate 0.18 upgrade — 2026-09-27

The deployment was upgraded from 0.17.2 to the latest stable release checked on
this date, **0.18.0-77a66e7 TensorRT**. The image is pinned rather than following
a mutable tag:

```
ghcr.io/blakeblackshear/frigate@sha256:82d7475ba7e5f950911bd9d06f2392de96881f39eeacd78824a526dde9b5cad9
```

Tailscale, camera firmware, Google access policy, recording retention, camera
credentials and the camera-side speaker scripts were not upgraded. Cam6 is
deliberately unplugged; it remains configured and reports an expected outage.

## Compatibility checks

- The new image supplies go2rtc 1.9.14 and FFmpeg 8.1.1 (installed under the
  `/usr/lib/ffmpeg/8.0/` path). Python remains 3.11.2, with `audioop` available
  and cryptography 44.0.3. Existing isolated SSH dependencies imported without
  replacement. A future Python 3.13 upgrade needs separate audioop handling.
- The 0.18 migrator was run against a private configuration copy. After YAML
  parsing, its only semantic change was `version: 0.18-0`. The deployed and
  published files retain their readable formatting and existing comments.
- A separate container recognized the RTX 4080 SUPER and successfully decoded,
  resized with `scale_cuda`, and encoded an eight-second data-saver test with
  NVENC. The existing explicit CUDA input/scale pipeline needs no added VAAPI
  device argument; the documented FFmpeg 8 `hwupload` issue was not reproduced
  by this pipeline.
- The recording bitstream rewrite and corrected live audio/video timestamps
  remain in place. This upgrade does not resolve upstream camera issue 593.
- The custom `/config/go2rtc` wrapper still invokes the bundled binary and
  inserts the container's actual IPv4 into the ICE binding filter. Arbitrary
  exec remains explicitly enabled for the restricted speaker bridges.

## Deployment and verification

Tailscale was stopped first, followed by Frigate. A full private configuration
directory backup, including the database, model cache and hidden speaker
credentials, was saved under the ignored `runtime/backups/` directory. Compose
files and an image manifest were also saved. SQLite `quick_check` passed on
the stopped database backup. The old image remains cached for rollback.

Frigate exceeded its 30-second stop grace period and Docker reported exit 137;
the backup was taken only after the container had stopped. Database integrity
checks passed before and after migration. New database migrations 033–035 and
the startup vacuum completed. Frigate was recreated and became healthy before
Tailscale was recreated to join the new network namespace.

The indexed recording gap was **170–178 seconds per powered camera**, around
19:12–19:15 Riyadh time. This includes shutdown, backup and database migration.

Validation:

- Five powered cameras resumed approximately 5 FPS capture; GPU inference was
  active. Both containers became healthy and the tunnel remained operational.
- Early cam2/cam4 samples contained macroblock decode errors. A subsequent
  sample of **three completed segments per powered camera (15 total)** decoded
  with FFprobe 8 without errors, with H.264 video and AAC audio. This is sample
  validation, not a claim that every recording is clean. The cause of the two
  early errors was not isolated.
- An initial FFmpeg-to-null check also reported output-muxer timestamp errors
  with both FFmpeg 7 and 8. Frame-count decoding with FFprobe avoids confusing
  those output warnings with input-frame corruption.
- Headless WebRTC tests received decoded video and audio and sent synthetic
  silence over PCMA to the speaker bridge for all five data-saver streams,
  plus cam1 full resolution. Sampled receive packet loss was zero. These used
  local signalling and the public VPS TCP media relay, not a fresh Google
  login or a real phone microphone.
- Cam5's first WebRTC speaker sample exited early; a subsequent direct
  six-second bridge test and another WebRTC test completed normally, without
  an additional bridge error. This transient is not proof of a version
  regression and should remain visible in the diagnostic record.
- Post-call checks on cams2–5 confirmed idle speakers, forced commands and
  key-only SSH. Cam1's existing credentials and restrictions were preserved.
- The independent VPS check passed its missing/wrong-secret rejection, viewer
  role, blocked user administration and redacted configuration checks. All
  powered cameras had fresh indexed recordings; only cam6 failed as expected.
- All **27 offline Python tests** passed inside the new image, using the
  deployment's isolated speaker dependencies.

Actual phone listening/talking and perceived delay still require a user check.
The above tests do not establish mouth-to-speaker latency or acoustic quality.

## Rollback

Do not merely replace the image tag after a database migration.

1. Acquire the same restart lock used by `scripts/restart-nvr.sh`. Stop
   Tailscale, then Frigate, and verify both are stopped.
2. Preserve the current configuration directory and Compose files separately
   for diagnosis. Restore the complete pre-upgrade configuration directory
   and old Compose file from the private backup, including the old database
   and its matching SQLite sidecars. Do not mix an old database with new WAL
   files. Never copy these backups into the public repository.
3. Confirm the old image is still present:
   `ghcr.io/blakeblackshear/frigate@sha256:8a364092b03561b9c08ac00730206e363a53d07ea0304f7d543b403b65432b5e`.
4. Recreate Frigate with `--pull never`, wait for health, then recreate
   Tailscale. Verify recording decode, live audio/video, speaker transport and
   gateway access restrictions independently.

Restoring the old database also restores its old recording index. Newer media
files remain on disk, but their post-backup index entries will not be in that
database. Preserve both versions and reconcile deliberately if rolling back.

## Intercom work after the upgrade

The 0.18 frontend still conditionally hides listening/talking controls when
stream metadata is incomplete. Its microphone toggle still rebuilds the
WebRTC connection; it is not a hold-to-talk implementation. The upgrade alone
does not resolve those interaction problems.

The proposed next step is a maintained modification inside Frigate: visible
Listen / Hold to talk / End controls, capability retry after playback starts,
explicit permission/error states, and one negotiated connection during the
intercom session. Transmission must stop on release, cancel, backgrounding or
navigation. The existing two-minute bridge limit must be represented in the
UI. That frontend customization has not been deployed with this upgrade.

References:
- [Official 0.18 release and migration notes](https://github.com/blakeblackshear/frigate/releases/tag/v0.18.0)
- [FFmpeg 8 hardware-transcoding caveat](https://docs.frigate.video/troubleshooting/go2rtc/#hardware-accelerated-transcoding-with-ffmpeg-8)
- [0.18 live camera view source](https://github.com/blakeblackshear/frigate/blob/v0.18.0/web/src/views/live/LiveCameraView.tsx)
- [0.18 WebRTC player source](https://github.com/blakeblackshear/frigate/blob/v0.18.0/web/src/components/player/WebRTCPlayer.tsx)
