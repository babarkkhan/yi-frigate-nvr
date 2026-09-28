# MStar 0.5.8 pilot — cam2, 2026-09-28

**Cam2 (living room, y203c) is running 0.5.8. Issue 593 still reproduces.**
The other cameras were not upgraded. Keep the recording rewrite workaround;
this trial does not justify a fleet rollout as a fix for the corruption.

## Package and installation

The maintainer announced an official release and recommended normal OTA in
[issue 593](https://github.com/roleoroleo/yi-hack-MStar/issues/593#issuecomment-5858250116).
[Release 0.5.8](https://github.com/roleoroleo/yi-hack-MStar/releases/tag/0.5.8)
was published September 27 at 18:47 UTC. The pilot used the unmodified official
`y203c_0.5.8.tgz`, SHA-256:

```
ba0432c2c238487d0e1213f587fda20b64db0562a6fd500e2622d9506d78e796
```

The downloaded checksum matched GitHub's asset digest, and a full readback
from the camera SD card matched again before invoking the updater. The old
0.5.7 package and a verified private archive of the installed `yi-hack`
directory, including settings, keys and custom scripts, were retained on the
host outside the public repository. The archive contained 361 entries and
all required recovery files were checked.

Initially no MStar camera had a mounted SD card. The owner inserted a 64 GB
card in cam2; its exFAT signature explained why the camera could not mount it.
After explicit approval to erase that card, the identified partition was
formatted FAT32 and mounted. No NVR media was formatted or deleted.

The upstream OTA scripts preserve normal settings but not our custom SSH
keys, host key, speaker script or `dropbear -R -s` startup modification.
For this pilot:

1. Saved those files privately and staged a camera-bound, one-time SD startup
   hook. The hook also supports restoring access on 0.5.7 if OTA fails to
   replace the firmware.
2. Set `SSHD=no` for the boot through OTA, keeping the existing running SSH
   session until reboot. This prevents the new unmodified startup script from
   launching a password-enabled listener before restoration.
3. Invoked the installed official `fw_upgrade.sh` with `get=upgrade`, using
   its supported local `y203c_x.x.x.tgz` path.
4. On first boot, restored the existing authorized keys, SSH host key and
   speaker script; patched only the new startup script's Dropbear command to
   `-R -s`; re-enabled SSH and started the key-only listener.
5. Verified unchanged host trust, byte-identical restored files, rejection of
   password login and rejection of arbitrary commands by the speaker key.
   Normal camera settings had no changed or added keys after restoration.
6. Archived the evidence, removed the one-time private SD restore material
   and firmware images left at the card root, and rechecked SSH restrictions.
   The SSH listener was restarted to release its temporary SD log; recording
   services were not restarted for this cleanup.

The OTA log warned about the pre-existing dangling `proxychains.conf` symlink.
The upgrade completed and the settings comparison passed; no proxy service
was enabled or introduced by this pilot.

Do not use ordinary OTA blindly on the other intercom cameras: the restore
steps are part of this installation, not functionality supplied by upstream.

## MP4 comparison: defect persists

Same test as the September 19 follow-up: FFmpeg 7.0, one direct RTSP/TCP input,
three simultaneous video-only stream-copy MP4 outputs requesting 12 seconds,
and `ffprobe -count_frames` decoding. The grabber used `-m y203c -r high -f`,
without `-s`, before and after the upgrade. Production recording filters
remained enabled throughout.

| Firmware | Output | Decoded frames | Invalid NAL-size messages | Split-NAL messages |
|---|---|---:|---:|---:|
| 0.5.7 | No bitstream filter | 6 | 448 | 234 |
| 0.5.7 | `filter_units=remove_types=99` | 220 | 0 | 0 |
| 0.5.7 | `h264_metadata` | 220 | 0 | 0 |
| 0.5.8 | No bitstream filter | 6 | 488 | 254 |
| 0.5.8 | `filter_units=remove_types=99` | 240 | 0 | 0 |
| 0.5.8 | `h264_metadata` | 240 | 0 | 0 |

All four filtered outputs had zero decoder diagnostic lines. Before/after
captures are different live intervals, so frame and error counts are not a
controlled measure of whether the defect became more severe. FFprobe returned
zero even for the corrupt files; its exit code alone is insufficient.

## Direct RTP comparison

The bounded Python RTSP/TCP capture does not use FFmpeg. An offline recheck
discards FU groups affected by sequence discontinuities before counting
complete reconstructed units.

| Observation | 0.5.7 | 0.5.8 |
|---|---:|---:|
| Capture duration | 15.01 s | 15.04 s |
| RTP packets | 1,620 | 1,471 |
| RTP payload format | All FU-A | All FU-A |
| FU-header NAL type | 0 in all packets | 0 in all packets |
| Sequence discontinuities | 0 | 3 |
| Complete units, excluding broken groups | 299 | 273 |
| Complete units with type 0 and embedded Annex-B start codes | 299 | 273 |

The first post-update parser output counted 276 units without discarding
broken groups. The corrected count is 273: three affected groups were
discarded, along with orphan fragments; the final unfinished group was also
excluded. The packet-level type-0 finding is independent of reassembly.
The cause of the three discontinuities was not isolated; they are not proof
of Wi-Fi loss or a firmware regression.

The camera still sends an Annex-B prefix where the reconstructed NAL header
should be, with further embedded start codes including SEI. Raw packets and
video are retained privately, not published.

The installed RTSP binary changed:

| Binary | Before SHA-256 | After SHA-256 |
|---|---|---|
| `rtsp_server_yi` | `70b42dda5fa1f2244bdf4f4d504486b342416c273daf20cf81879406562a1c1c` | `adc7e71eac1ff1c48675253d9c31e3e9e450a7443d9dea43d10607f96e76ab49` |
| `h264grabber_h` | `8da865093189fadd93dcbd0e838b1eb297bcb036e47c9171748b0eb15a6f4b6b` | same |

This confirms an updated installed server, not its exact source revision.
The package has not been mapped to a unique `yi` branch build commit.

## Audio and operational checks

- Cam2 still advertises mono `pcm_s16be`, 8000 Hz, with `RTSP_AUDIO=yes`.
  A ten-second audio request decoded **10.0 seconds**, taking 10.85 wall
  seconds: decoded/requested = **1.0**, rather than the historical 1.99
  measurement on 0.5.7. There was no fresh immediately-before audio pacing
  measurement in this trial, so treat the old value as a historical comparison.
  The existing live timestamp normalization is retained; it remains compatible.
- Headless WebRTC tests passed for cam2 data saver (960 wide) and full
  resolution (1920 wide). Both received decoded video and audio and sent PCMA
  synthetic silence through the speaker bridge. Both sampled zero receive
  packet loss. This proves transport compatibility, not audible speaker quality
  or phone latency; the owner deferred the physical listening/talking check.
- A recent recording and a later three-segment sample decoded with no errors,
  containing H.264 and AAC. No production bitstream filter was removed.
- Independent gateway checks found five powered cameras capturing around
  5 FPS with fresh indexed recordings and the existing access restrictions
  intact. Cam6 remains intentionally unplugged.
- The OTA recording gap was **174.1 seconds**, 19:00:00.895–19:02:55 UTC
  (22:00–22:03 Riyadh). An earlier **82.9-second** gap occurred during card
  preparation, when the camera restarted.
- A further **23.8-second** recording gap occurred at 19:08:14–19:08:38 UTC
  during live testing. Frigate logged RTSP connection refusals. Camera uptime
  continued, while grabber and RTSP process IDs changed: the streaming
  processes restarted without a full camera reboot. It recovered automatically.
  No manual RTSP restart was issued. Cause and connection to diagnostic load
  remain unresolved; this is not a clean stability soak.

## Decision and follow-up

Leave cam2 as the only 0.5.8 pilot, retain its production filters and existing
audio normalization, and keep the other firmware versions unchanged. Audible
acceptance is pending. Report the persistence of type-0 FU headers and MP4
corruption to the maintainer, including the exact release and binary hashes,
and request the intended source revision/fix. No new GitHub comment was sent
as part of this pilot.

Rollback materials are retained privately. A downgrade should use the reviewed
local-package OTA path with the same secure restoration precautions, followed
by recording, audio and SSH checks; simply flashing 0.5.7 would also replace
the custom scripts. The rollback procedure was prepared, not exercised.
