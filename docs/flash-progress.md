# Flash progress - COMPLETE, 6 of 6, 2026-08-22

| # | Name | Serial | IP | MAC vendor | Platform | Hack | Stream |
|---|---|---|---|---|---|---|---|
| 1 | men's room | BFUSY21xxxxxxxxxxxx | 192.168.3.5 | Sichuan AI-Link | MStar y203c | 0.5.7 | 1920x1088 |
| 2 | living room | BFUSY21xxxxxxxxxxxx | 192.168.3.22 | Sichuan AI-Link | MStar y203c | 0.5.7 | 1920x1088 |
| 3 | kitchen | BFUSY31xxxxxxxxxxxx | 192.168.3.3 | Shenzhen Bilian | Allwinner y20ga | 0.4.0 | 1920x1080 |
| 4 | hallway | BFUSY21xxxxxxxxxxxx | 192.168.3.4 | Sichuan AI-Link | MStar y203c | 0.5.7 | 1920x1088 |
| 5 | laundry | BFUSY21xxxxxxxxxxxx | 192.168.3.149 | Sichuan AI-Link | MStar y203c | 0.5.7 | **RTSP DOWN** |
| 6 | extra | BFUSY31xxxxxxxxxxxx | 192.168.3.6 | Shenzhen Bilian | Allwinner y20ga | 0.4.0 | 1920x1080 |

Six for six. No bricks, no failed flashes, no wrong packages.

Every camera self-reports the `model_suffix` that was predicted from the
serial-prefix + firmware-version match, on both platforms.

## The identification chain held up

The MAC vendor split predicted the platform split exactly:

- `60:23:A4` Sichuan AI-Link x4 -> MStar y203c   -> cams 1, 2, 4, 5
- `7C:A7:B0` Shenzhen Bilian  x2 -> Allwinner y20ga -> cams 3, 6

And the serial body predicted it independently:

- `BFUS`**`Y21`**`xxxxx` -> MStar y203c
- `BFUS`**`Y31`**`xxxxx` -> Allwinner y20ga

Three independent signals - MAC vendor, serial body, firmware version - agreed
on every camera. Worth reusing if more Yi cameras are ever added.

## Platform differences observed

| | MStar y203c | Allwinner y20ga |
|---|---|---|
| Resolution | 1920x**1088** | 1920x**1080** |
| Audio in RTSP | PCM mu-law present | not seen on ch0_0 |
| Flash duration | ~3 min | ~3-20 min (much faster than the documented hour) |
| Reversible | no, overwrites flash | yes, remove SD card |
| Backup produced | none | full mtdblock0-7 dump on the card |
| hostname default | `yi-hack` | `xiaoyi` |

## Firmware backups captured

`camera-backups/cam6-extra-BFUSY31xxxxxxxxxxxx/` - full mtdblock0-7 of a working
y20ga on stock 12.2.0.5. This is the artifact roleoroleo requested twice
upstream (issues #1112, #1125) and never received. Cam 3's equivalent should
be captured from the card as well.

## Outstanding

1. **Cam 5 RTSP daemon is dead** and has not self-recovered. See
   `rtsp-stability.md`. Restart without reboot:
   `/cgi-bin/service.sh?name=rtsp&action=stop` then
   `/cgi-bin/service.sh?name=rtsp&action=start&param1=null&param2=null`
2. **Config pass on all six** - every camera is still at fresh-flash defaults:
   `DISABLE_CLOUD:no`, `TELNETD:yes`, `FTPD:yes`, empty SSH password.
   The cameras are flashed but still talking to Yi's servers.
3. Allwinner cameras have extra config keys the MStar ones do not
   (`SNAPSHOT_LOW`, `RTSP_STI`, `SPEAKER_AUDIO`, `ONVIF`). Verify
   `configure-cam.ps1` against a y20ga before assuming it applies unchanged.
