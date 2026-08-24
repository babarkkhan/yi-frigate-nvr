# Camera fleet - final state, 2026-08-22

All six cameras flashed, configured, hardened, and verified.

| # | Name | Hostname | IP | Platform | Hack | Stream |
|---|---|---|---|---|---|---|
| 1 | men's room | yi-cam1-mensroom | 192.168.3.5 | MStar y203c | 0.5.7 | 1920x1088 + audio |
| 2 | living room | yi-cam2-living | 192.168.3.22 | MStar y203c | 0.5.7 | 1920x1088 + audio |
| 3 | kitchen | yi-cam3-kitchen | 192.168.3.3 | Allwinner y20ga | 0.4.0 | 1920x1080 |
| 4 | hallway | yi-cam4-hallway | 192.168.3.4 | MStar y203c | 0.5.7 | 1920x1088 + audio |
| 5 | laundry | yi-cam5-laundry | 192.168.3.149 | MStar y203c | 0.5.7 | 1920x1088 + audio |
| 6 | extra | yi-cam6-extra | 192.168.3.6 | Allwinner y20ga | 0.4.0 | 1920x1080 |

## Configuration applied to all six

    DISABLE_CLOUD : yes     no longer contacts Yi's servers
    TELNETD       : no      port 23 closed
    FTPD          : no      port 21 closed
    SSHD          : no      port 22 closed (SSH_PASSWORD was empty on all six)
    RTSP          : yes     port 554
    RTSP_STREAM   : high
    HOSTNAME      : per-camera

Open ports on every camera, verified: **80 and 554 only.**

SSH was disabled rather than password-protected. Nothing in the Frigate design
needs it, and every camera shipped with an empty SSH password. Re-enable via
`set_configs.sh?conf=system` with `{"SSHD":"yes","SSH_PASSWORD":"..."}` if it
is ever needed for debugging.

## Consequence: the Yi app no longer works

That is the intended outcome. Camera management is now the per-camera CGI at
`http://<ip>/cgi-bin/...`, and Frigate will be the viewing interface.

## RTSP endpoints for Frigate

    rtsp://192.168.3.5/ch0_0.h264      cam1 men's room
    rtsp://192.168.3.22/ch0_0.h264     cam2 living room
    rtsp://192.168.3.3/ch0_0.h264      cam3 kitchen
    rtsp://192.168.3.4/ch0_0.h264      cam4 hallway
    rtsp://192.168.3.149/ch0_0.h264    cam5 extra
    rtsp://192.168.3.6/ch0_0.h264      cam6 laundry

`ch0_1.h264` (substream) returns 404 - only one stream is enabled, deliberately.
See rtsp-stability.md.

## Known fragility - cam 1 especially

Cam 1 has now failed 2 of 3 rapid stream probes and succeeded on every retry.
Both failures came while the camera was under load (load_avg 1.88, shortly
after boot). Cam 5's RTSP daemon died outright earlier and needed a reboot.

These SoCs are weak. The NVR must:
- pull each camera exactly once via go2rtc, with unlimited reconnect
- avoid probing several cameras simultaneously
- treat "HTTP responds but RTSP does not" as a distinct failure state
- be able to restart the RTSP daemon over HTTP, and reboot the camera if that fails

## Measured storage figures

Main stream measured at **1.19 Mbps** (15s capture, video only, MStar camera).

    per camera/day  : 12.8 GB
    6 cameras/day   : 76.9 GB
    6 cameras x 3d  : 231 GB

1 TB is comfortable for 3-day continuous plus the alert/detection tiers.

## Still to do

- [ ] Capture cam 3's mtdblock backup from the SD card (cam 6's is saved)
- [ ] DHCP reservations for all six in the Huawei router
- [ ] Block cameras' internet at the router - belt and braces alongside DISABLE_CLOUD
- [ ] Acquire the Beelink EQ14 + 1 TB NVMe
- [ ] Build the Frigate stack
