# Flashing runbook

## DO NOT factory-reset the cameras

Resetting gains nothing and can strand a camera.

1. **A reset does not downgrade firmware.** You stay on 4.5.0.0C / 12.2.0.5.
   It undoes nothing relevant to this project.
2. **The MStar cameras need their existing wifi credentials.** The
   `y203c_0.5.7.tgz` package contains exactly two files — `sys_y203c` and
   `home_y203c` — and no wifi configuration file. The project wiki page for
   setting wifi credentials is titled "Change WiFi credentials (deprecated
   from 0.4.0)"; we are installing 0.5.7. Install step 8 simply assumes wifi
   connects. A reset camera has no credentials and no documented SD-card way
   to supply them.
   *(Caveat: that wiki page would not render, so this is inferred from package
   contents plus the deprecation note. The risk is one-sided — resetting buys
   nothing, so don't.)*
3. **The Allwinner camera wants pairing done first.** Its README: "If you want
   to use the original Yi app, please install it and complete the pairing
   process before installing the hack."

**Do this instead: block the cameras' internet access at the router.** That
stops the cloud streaming and the auto-updates — the two things you actually
want — while keeping wifi credentials and LAN reachability intact.

## Risk is very different between the two platforms

| | MStar — cams 1,2,4,5 | Allwinner — cam 3 |
|---|---|---|
| Nature | **Permanently overwrites** stock firmware | Runs from the SD card |
| README says | "This firmware completely overwrite the original firmware. So, USE AT YOUR OWN RISK." | "This hack is not a permanent change, remove your SD card and the cam will come back to the original state." |
| Revert | Re-flash with another version | **Pull the SD card** |
| Pre-flash backup | none documented | documented, read-only |

So the four MStar flashes carry real risk and the kitchen one is nearly
risk-free. Test on **cam 5 "extra"** — the spare, and a y203c like 4 of your 5.

## Packages (downloaded 2026-08-22, in ./firmware/)

| File | For | SHA-256 |
|---|---|---|
| `y203c_0.5.7.tgz` | cams 1,2,4,5 | `e7b7e5dcd12a9b8d909662c3d50518de4a5e87674377b65d8316d396dd930c0a` |
| `y20ga_0.4.0.tgz` | cam 3 kitchen | `f0b7791acae039f35bb539a23cb97185643733de77ee237c182748fa68638502` |

Contents verified:

    y203c_0.5.7.tgz ->  sys_y203c
                        home_y203c

    y20ga_0.4.0.tgz ->  Factory/{config.sh, factory_test.sh,
                                 configure_wifi.sh, configure_wifi.cfg.ori}
                        home_y20gam.stage
                        newhome/base/tools/extpkg.sh

Note `home_y20ga**m**.stage` — the "m" variant. This matches Yi's own firmware
filename for cam 3's exact build (`12.2.0.5_202411131404home_y20gam`, from
Yi's OSS server). That is near-conclusive confirmation this is the right
package for the kitchen camera.

## Prerequisites

- **microSD card, 32 GB or smaller, FAT32.** Windows will not natively format
  above 32 GB as FAT32. One card is enough — reused for each camera.
- Both READMEs recommend **formatting the card in the camera itself**, using
  the Yi app's native format function. Do this *before* blocking internet, in
  case the app needs the cloud to drive it.
- Physical access to power-cycle each camera.
- Router admin at `http://192.168.3.1`.

## Order of operations

### Phase A — before touching any firmware
1. Insert the SD card in cam 5, format it via the Yi app's format function.
2. In the router, note each camera's IP and **set a DHCP reservation** for each.
3. **Block all five cameras' internet access** at the router. Keep them on the
   LAN — block WAN only.
4. Confirm they are still reachable on the LAN (they should still ping).

### Phase B — cam 5 "extra" as the test article
5. Copy `sys_y203c` and `home_y203c` to the **root** of the FAT32 card.
   Nothing else on the card.
6. Power off cam 5. Insert card. Power on.
7. Yellow light flashes ~30 seconds — firmware being written. Camera reboots.
8. Yellow light again for the final stage — up to 2 minutes.
9. Blue light = wifi connected.
10. Open `http://<cam5-ip>` — the hack's web UI should load.
11. Set a password in the web UI. Enable **RTSP**. Disable cloud if offered.
12. Verify from this PC before going further:

        ffprobe rtsp://<cam5-ip>/ch0_1.h264
        ffplay  rtsp://<cam5-ip>/ch0_0.h264

    Record the actual bitrate and resolution — that replaces the storage
    estimate in the sizing notes.

### Phase C — roll out
13. Repeat Phase B for cams 1, 2, 4 (same package, same steps).
14. Cam 3 kitchen last: extract `y20ga_0.4.0.tgz` to the card root, insert,
    reboot, and **wait up to an hour** through several reboots. Done when the
    light is solid blue for at least a minute. Do not power-cycle.
    Optional: set wifi first by renaming `Factory/configure_wifi.cfg.ori` to
    `configure_wifi.cfg` and editing it.

## If something goes wrong

- **Cam 3 (Allwinner):** pull the SD card and power-cycle. It reverts.
- **Cams 1,2,4,5 (MStar):** re-run the hack with a different release version.
  Unbrick guide: https://github.com/roleoroleo/yi-hack-MStar/wiki
- Do not power-cycle mid-flash. That is the actual way these get bricked.

## Expected RTSP endpoints after flashing

    rtsp://CAMERA_IP/ch0_0.h264    main / high
    rtsp://CAMERA_IP/ch0_1.h264    sub / low   <- use for Frigate detection
