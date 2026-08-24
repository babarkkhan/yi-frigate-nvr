YI CAMERA FLASH KIT
Built 2026-08-22. Everything needed to prime an SD card on another machine.

-------------------------------------------------------------------------------
WHICH FOLDER FOR WHICH CAMERA
-------------------------------------------------------------------------------

  Cam 1  men's room    BFUSY21xxxxxxxxxxxx   fw 4.5.0.0C   -> MStar_y203c__cams_1_2_4_5
  Cam 2  living room   BFUSY21xxxxxxxxxxxx   fw 4.5.0.0C   -> MStar_y203c__cams_1_2_4_5
  Cam 3  kitchen       BFUSY31xxxxxxxxxxxx   fw 12.2.0.5   -> Allwinner_y20ga__cam3_kitchen
  Cam 4  hallway       BFUSY21xxxxxxxxxxxx   fw 4.5.0.0C   -> MStar_y203c__cams_1_2_4_5
  Cam 5  extra         BFUSY21xxxxxxxxxxxx   fw 4.5.0.0C   -> MStar_y203c__cams_1_2_4_5

  START WITH CAM 5. It is the spare, and it uses the same package as 4 of your 5.

-------------------------------------------------------------------------------
THE EASY WAY
-------------------------------------------------------------------------------

Open PowerShell in this folder, with the SD card inserted, and run:

    powershell -ExecutionPolicy Bypass -File prime-sd.ps1 -Drive G -Model MStar

Replace G with the SD card's actual drive letter. For the kitchen camera use
-Model Allwinner instead.

The script refuses to run unless the card is FAT32 and empty. It only copies --
it never formats and never deletes. It verifies every file by SHA-256 after
copying and tells you the LED sequence to expect.

-------------------------------------------------------------------------------
THE MANUAL WAY (if PowerShell is blocked)
-------------------------------------------------------------------------------

SD card must be FAT32 and completely empty. exFAT WILL NOT WORK -- the flash
appears to do nothing. That is the single most common failure.

For cams 1, 2, 4, 5 -- copy these 2 files to the ROOT of the card:
    MStar_y203c__cams_1_2_4_5\sys_y203c
    MStar_y203c__cams_1_2_4_5\home_y203c

For cam 3 kitchen -- copy the CONTENTS of Allwinner_y20ga__cam3_kitchen to the
root of the card, preserving folders:
    Factory\           (4 files)
    newhome\           (contains base\tools\extpkg.sh)
    home_y20gam.stage

Nothing else on the card. No stray folders.

-------------------------------------------------------------------------------
FLASHING
-------------------------------------------------------------------------------

MStar cams (1, 2, 4, 5) -- about 3 minutes:
   1. Power OFF the camera.
   2. Insert card.
   3. Power ON.
   4. Yellow LED flashes ~30 seconds -- firmware writing. Camera reboots.
   5. Yellow LED again, up to 2 minutes -- final stage.
   6. Blue LED -- wifi connected. Done.
   7. Browse to http://<camera-ip>  (find the IP in the router's device list)

   WARNING: this permanently overwrites the stock firmware. To recover, re-run
   the hack with a different release version.

Cam 3 kitchen (Allwinner) -- UP TO ONE HOUR:
   1. Power OFF. Insert card. Power ON.
   2. Several reboots are normal. Be patient.
   3. Done when the LED is solid blue for at least a full minute.
   4. DO NOT power-cycle during this. That is how cameras get bricked.
   5. Browse to http://<camera-ip>

   This one is reversible -- pull the SD card and it returns to stock.

   Optional, before inserting: rename Factory\configure_wifi.cfg.ori to
   Factory\configure_wifi.cfg and put your wifi SSID/password in it.

-------------------------------------------------------------------------------
AFTER IT BOOTS
-------------------------------------------------------------------------------

In the camera's new web interface:
   - set a password
   - enable RTSP
   - disable the cloud connection if the option is offered

Then confirm the stream works. Expected URLs:
   rtsp://<camera-ip>/ch0_0.h264    main / high quality
   rtsp://<camera-ip>/ch0_1.h264    sub / low quality

-------------------------------------------------------------------------------
DO NOT
-------------------------------------------------------------------------------

  - Do NOT factory-reset the cameras. The MStar package has no wifi config
    file; a reset camera may be unreachable after flashing.
  - Do NOT tap "Update" in the Yi app on any camera. Newer firmware is not
    supported and there is no downgrade path.
  - Do NOT use exFAT.
  - Do NOT power-cycle mid-flash.
  - Do NOT put the MStar files on the kitchen camera or vice versa.

-------------------------------------------------------------------------------
CONTENTS
-------------------------------------------------------------------------------

  prime-sd.ps1                      the copy + verify script
  SHA256SUMS.txt                    hashes of everything in this kit
  MStar_y203c__cams_1_2_4_5\        firmware for cams 1,2,4,5
  Allwinner_y20ga__cam3_kitchen\    firmware for cam 3
  archives\                         original .tgz downloads (fallback)
  docs\                             full inventory, runbook, network scan

Sources:
  https://github.com/roleoroleo/yi-hack-MStar        release 0.5.7
  https://github.com/roleoroleo/yi-hack-Allwinner    release 0.4.0
