# Cam 5 "extra" — post-flash report, 2026-08-22

**Flash successful.** IP `192.168.3.149` (new DHCP lease).

## Identity confirmed

From `http://192.168.3.149/cgi-bin/status.json`:

    name          : yi-hack-mstar
    fw_version    : 0.5.7                     <- our hack, correct release
    home_version  : 4.5.0.0C_201910080934     <- original stock, preserved
    model_suffix  : y203c                     <- model identification was correct
    serial_number : BFUSY21xxxxxxxxxxxx      <- matches cam 5 "extra" (BFUSY21xxxxxxxxxxxx)
    hostname      : yi-hack
    go2rtc        : no

The serial matches the inventory exactly. Right camera, right package.

## Streams

| Endpoint | Result |
|---|---|
| `rtsp://192.168.3.149/ch0_0.h264` | H.264 **1920x1088 @ 20fps** + PCM mu-law audio 64 kbps |
| `rtsp://192.168.3.149/ch0_1.h264` | **404 Stream Not Found** — low stream not enabled |
| `cgi-bin/snapshot.sh?res=high` | 200, JPEG 1920x1088, ~183 KB |
| `cgi-bin/snapshot.sh?res=low` | 200, JPEG **640x360**, ~34 KB |

The low-resolution path exists in hardware — the substream is simply not enabled.

## Measured bitrate — replaces the earlier estimate

15-second capture of the main stream, video only:

    video bitrate  : 1.19 Mbps     (estimate had been ~1.5)
    per camera/day : 12.8 GB
    5 cameras/day  : 64.1 GB
    5 cameras x 3d : 192 GB

A 1 TB drive is comfortable. Continuous 3-day retention for all five plus the
14-day alert and 7-day detection tiers fits with a lot of room to spare.

## Open ports

    21  FTP      enabled
    22  SSH      enabled, SSH_PASSWORD is EMPTY
    23  telnet   enabled
    80  HTTP     CGI works; static web UI returns 404 (see below)
    554 RTSP     working

## Current configuration

From `cgi-bin/get_configs.sh?conf=system`:

    RTSP          : yes
    RTSP_STREAM   : high        <- why ch0_1 404s
    RTSP_AUDIO    : yes
    DISABLE_CLOUD : no          <- CLOUD IS STILL ACTIVE
    TELNETD       : yes
    FTPD          : yes
    SSHD          : yes
    SSH_PASSWORD  : (empty)
    MQTT          : no
    HOSTNAME      : yi-hack

## Changes needed

1. **`DISABLE_CLOUD` -> yes.** This is the entire point of the project and it is
   currently off. The upstream README also notes "Disable cloud is recommended
   to save resources."
2. **`TELNETD` -> no, `FTPD` -> no**, and set an SSH password. Telnet and FTP
   are open with no credentials configured.
3. **RTSP stream selection** — see the constraint below.

`cgi-bin/set_configs.sh` responds 200, so all of this is settable over HTTP
without the web UI.

## Constraint: only one RTSP stream should be enabled

yi-hack-MStar README, line 142:

    "If you enable all the services you may have some problems.
     For example, enabling both rtsp streams is not recommended."

This breaks the original plan's design, which assumed a low substream for
Frigate detection **and** the main stream for recording, simultaneously.

### Revised approach — main stream only

Keep `RTSP_STREAM: high` and let Frigate do the downscaling:

- one camera pull, restreamed by go2rtc, shared by both consumers
- `detect` role on the same stream, with `detect.width/height` set to 640x360
- `record` role stream-copies the 1080p, no re-encode

Cost: the host decodes 1920x1088@20 per camera instead of 640x360. Five cameras
is ~100 fps of 1080p H.264 decode — well within an N150's QuickSync via VAAPI.
This is precisely the workload the iGPU was chosen for, so it is not a problem,
but it does make hardware decoding mandatory rather than optional.

Do NOT enable both streams to avoid this. The camera SoC is the weak link.

## Web UI

Every static path returns 404 (`/`, `/index.html`, `/main.html`, ...) while
`/cgi-bin/*` works and `/cgi-bin/` returns 403. So httpd is running and its
cgi-bin is populated, but the static UI assets are not being served.

Not blocking — everything is reachable via CGI — but worth trying in a real
browser before concluding it is broken.

## Note for the remaining cameras

`RTSP_STREAM` defaults to `high` and `DISABLE_CLOUD` defaults to `no` on a
fresh flash. Both will need setting on cams 1, 2 and 4 as well.
