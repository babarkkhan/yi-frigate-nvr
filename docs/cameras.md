# Camera inventory — resolved 2026-08-22

| # | Name | Serial | Stock firmware | Platform | Model | Project | Package | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | men's room | BFUSY21xxxxxxxxxxxx | 4.5.0.0C_201910080934 | MStar | y203c | yi-hack-MStar 0.5.7 | `y203c_0.5.7.tgz` | **SUPPORTED** |
| 2 | living room | BFUSY21xxxxxxxxxxxx | 4.5.0.0C_201910080934 | MStar | y203c | yi-hack-MStar 0.5.7 | `y203c_0.5.7.tgz` | **SUPPORTED** |
| 3 | kitchen | BFUSY31xxxxxxxxxxxx | 12.2.0.5_202411131404 | Allwinner | y20ga | yi-hack-Allwinner 0.4.0 | `y20ga_0.4.0.tgz` | **LIKELY** |
| 4 | hallway | BFUSY21xxxxxxxxxxxx | 4.5.0.0C_201910080934 | MStar | y203c | yi-hack-MStar 0.5.7 | `y203c_0.5.7.tgz` | **SUPPORTED** |
| 5 | extra | BFUSY21xxxxxxxxxxxx | 4.5.0.0C_201910080934 | MStar | y203c | yi-hack-MStar 0.5.7 | `y203c_0.5.7.tgz` | **SUPPORTED** |

## Matching evidence

yi-hack-MStar README line 153 — exact match for cams 1, 2, 4, 5:

    | **Yi 1080p Home BFUS** | 4.5.0* | y203c | - |

yi-hack-Allwinner README line 141 — match for cam 3:

    | **Yi 1080p Home BFUS** | 12.2.0* | y20ga | - |

### Independent confirmation: the serial pattern

The serials split exactly along the firmware/platform line:

- `BFUS`**`Y21`**`xxxxx` -> 4.5.0.0C -> MStar y203c    (cams 1, 2, 4, 5)
- `BFUS`**`Y31`**`xxxxx` -> 12.2.0.x -> Allwinner y20ga (cam 3)

This matches third-party reports: `BFUSY31xxxxxxxxxxxx` on 12.2.0.2 and
`BFUSY31xxxxxxxxxxxx` on 12.2.0.5 are both Allwinner y20ga cameras
(yi-hack-Allwinner-v2 issue #1125).

**Careful:** the `Y21` in serials 1/2/4/5 does NOT mean model `y21ga`. It is a
serial batch code. Those cameras are MStar `y203c`. The firmware version is the
authoritative discriminator, not the serial digits.

## Project health (checked 2026-08-22)

| Project | Latest release | Last commit |
|---|---|---|
| yi-hack-MStar | 0.5.7 — 2026-01-03 | 2026-08-09 |
| yi-hack-Allwinner | 0.4.0 — 2025-10-27 | — |

Note: the MStar README carries a "I have no time to support the project"
disclaimer, but the commit history contradicts it — last commit was 13 days
ago and there was a release in January 2026. Treat the project as active.

## URGENT — updates are being pushed right now

| # | Current | Update offered | Risk |
|---|---|---|---|
| 1,2,4,5 | 4.5.0.0C_201910080934 | 4.5.0.0C_**202608061757** | dated 2026-08-06 — two weeks ago |
| 3 | 12.2.0.5_202411131404 | 12.2.0.6_202607201743 | **12.2.0.6 is in no supported row** |

**Do not tap Update on any camera. Block all five from the internet at the
router as the first action of this project.**

For cams 1/2/4/5 the offered build keeps the same `4.5.0.0C` prefix, so it
would nominally still match `4.5.0*` — but that is exactly the assumption that
broke on Allwinner, where 12.1.19 worked and 12.2.x silently broke the init
chain. The 2019 build is the one the community has actually tested. Stay on it.

## Flash procedures differ by platform

### MStar (cams 1, 2, 4, 5) — fast, ~3 minutes
1. Format SD as FAT32, preferably using the camera's own format function.
2. Extract `y203c_0.5.7.tgz` to the card root (yields `home_y203c`, `sys_y203c`).
3. Insert card, reboot camera.
4. Yellow light flashes ~30 seconds — firmware being written. Camera boots.
5. Yellow light again for the final stage — up to 2 minutes.
6. Blue light = wifi connected.
7. Open `http://CAMERA_IP`.

### Allwinner (cam 3) — slow, up to an hour
1. Pair in the Yi app first if you want the app to keep working.
2. Format SD as FAT32 using the camera's format function.
3. Extract `y20ga_0.4.0.tgz` to the card root
   (yields `Factory/`, `newhome/`, `home_y20ga.stage`).
4. Optional wifi: rename `Factory/configure_wifi.cfg.ori` to `.cfg`, edit.
5. Insert card, reboot.
6. **Wait up to an hour.** Several reboots are normal. Do not power-cycle.
   Done when the light is solid blue for at least a minute.
7. Open `http://CAMERA_IP`.

## Recommended order

1. Block all five cameras' internet access at the router.
2. Take a read-only backup dump of each.
3. Flash **cam 5 "extra"** first — it is the spare, so lowest stakes, and it is
   a y203c, which is 4 of your 5 cameras. Best possible test article.
4. Verify RTSP with ffprobe before flashing anything else.
5. Flash cams 1, 2, 4.
6. Flash cam 3 last — different project, different procedure, longer wait.
