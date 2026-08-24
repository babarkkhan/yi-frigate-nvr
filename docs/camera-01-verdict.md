# Camera 01 — verdict: LIKELY FLASHABLE (revised 2026-08-22)

- Serial prefix: BFUS
- Stock firmware: **12.2.0.5_202411131404**
- Update offered in app: 12.2.0.6_202607201743  <-- DO NOT INSTALL
- Platform: Allwinner
- **Model code: y20ga** (not y21ga — see below)
- **Project: yi-hack-Allwinner (v1)**, release 0.4.0, asset `y20ga_0.4.0.tgz`

## Correction to the earlier verdict

An earlier note here said this camera was unflashable, on the basis that
yi-hack-Allwinner-v2 supersedes yi-hack-Allwinner. **That was wrong.** The two
projects cover *different camera models*, not different generations of the same
work. v1 is not obsolete — it is the only project covering y20ga, and it had a
release in October 2025.

## Why y20ga, not y21ga — the firmware version discriminates

Both models use the BFUS serial prefix, so the prefix cannot tell them apart.
The supported firmware ranges are disjoint, and that is what settles it:

| Model | Project | Supported stock firmware |
|---|---|---|
| y21ga | Allwinner-**v2** | `9.0.19*`, `12.1.19*` |
| **y20ga** | Allwinner-**v1** | `8.2.0*`, **`12.2.0*`** |

`12.2.0.5` matches `12.2.0*` — a y20ga row. It matches no y21ga row.

Three independent confirmations:

1. yi-hack-Allwinner README line 141:
   `| **Yi 1080p Home BFUS** | 12.2.0* | y20ga | - |`
2. Yi's own firmware server serves this exact build under the y20ga family:
   `.../smarthomecam/familymonitor-y20ga/311/12.2.0.5_202411131404home_y20gam`
3. Maintainer roleoroleo to a user who also believed they had a y21ga
   (Allwinner-v2 #1125, 2026-07-16):
   > "Pay attention. Your cam is a y20ga and it's covered by another
   > (previous) project. https://github.com/roleoroleo/yi-hack-Allwinner
   > Using that hack, it should work without any change."

This is a known trap: users assume y21ga, flash the y21ga package, and get a
silent failure. See "the trap" below.

## The trap that produced the earlier wrong reading

Allwinner-v2 issues #1112 and #1125 both describe BFUS cameras on 12.2.0.5
where the hack appears to apply (`Factory.done` created, telnetd injected)
but no services start. Root cause, diagnosed by user rrader in #1125:

- `/etc/init.d/S02app` mounts mtdblock3 to /home and runs `/home/app/init.sh`
- in 12.2.x, `/home/app/init.sh` **no longer references `/backup/init.sh`**
- so the hack is installed but nothing ever executes it

Those users were applying the **y21ga** package to a **y20ga** camera. The fix
is not a workaround — it is using the correct project.

## Failure mode is soft, not a brick

On the reports above the camera stayed fully functional on stock firmware and
in the Yi app. A wrong-package attempt wastes time, not hardware.

## Procedure (yi-hack-Allwinner v1, from its README)

Note this differs from the v2 project's procedure — and takes far longer.

1. If you want to keep using the Yi app, **pair the camera first**, before hacking.
2. Format the SD card FAT32 — **preferably using the camera's own format function**.
3. Download `y20ga_0.4.0.tgz` from the v1 project's Releases.
4. Extract to the SD card root. Should yield: `Factory/`, `newhome/`, `home_y20ga.stage`
5. Optional wifi: rename `Factory/configure_wifi.cfg.ori` to `.cfg` and edit.
6. Insert card, reboot camera.
7. **Wait — it can take up to an hour** and will reboot several times.
   Done when the light is solid blue for at least a minute. Do not power-cycle.
8. Open `http://CAMERA_IP` to confirm.

## Do the backup dump first — it is read-only

https://github.com/roleoroleo/yi-hack-Allwinner/wiki/Dump-your-backup-firmware-(SD-card)

`backup.tar.gz` to a FAT32 card, boot, power off, retrieve `/backup`. Writes
nothing to the camera. The hack also makes its own backup, but the README
recommends taking your own first anyway.

## Known-bad prior art — do NOT use the pre-hacked image

Allwinner-v1 #447 contains `home_y20ga.gz`, a pre-hacked 12.2.0.5 image posted
by roleoroleo. **Two users reported it doing nothing** (divadiow, konqueror81);
one ended up bootlooping and needing the unbrick procedure. It is not a
supported route. Use the standard `y20ga_0.4.0.tgz` install instead.

## Actions

- [ ] DO NOT tap Update. 12.2.0.6 is NOT in any supported row; 12.2.0.5 IS.
- [ ] Block camera internet at the router to prevent auto-update.
- [ ] Take a backup dump.
- [ ] Flash `y20ga_0.4.0.tgz` on this camera as the test case.
- [ ] Read the other three cameras' firmware versions before touching them.

## Sources
- https://github.com/roleoroleo/yi-hack-Allwinner (README raw, master; release 0.4.0)
- https://github.com/roleoroleo/yi-hack-Allwinner/issues/447
- https://github.com/roleoroleo/yi-hack-Allwinner-v2/issues/1125
- https://github.com/roleoroleo/yi-hack-Allwinner-v2/issues/1112
