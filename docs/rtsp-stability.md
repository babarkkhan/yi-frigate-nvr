# RTSP daemon instability - observed 2026-08-22

## What happened

Cam 5 (192.168.3.149) served RTSP correctly for roughly 45 minutes after
flashing, then stopped. State at the time of discovery:

    uptime      : 3317s (55 min) - the camera did NOT reboot
    HTTPD       : responding normally
    RTSP config : "RTSP":"yes", "RTSP_PORT":"554"
    port 554    : CLOSED
    ffprobe     : no response
    load_avg    : 1.11 1.26 1.37

So the configuration is intact and the camera is healthy - the **RTSP daemon
itself died and was not restarted**. There is no supervisor watching it.

Earlier warning sign: during a sweep that probed all four MStar cameras in
quick succession, cam 1 briefly returned no streams, then recovered on retry.
Same daemon, same fragility.

## Why this matters for the Frigate build

This is not a one-off. It means **camera-side RTSP must be treated as
unreliable**, and the design has to account for it:

1. go2rtc on the NVR must pull each camera exactly once and be configured to
   reconnect indefinitely.
2. Health checks must alert on a camera whose stream is gone, since the camera
   will happily sit there answering HTTP while serving nothing.
3. A recovery action is needed - restart the daemon over HTTP, and reboot the
   camera if that fails.

Frigate will show the camera as offline, but nothing will fix it automatically.

## Restarting the RTSP daemon without rebooting

From `src/static/static/home/yi-hack/script/service.sh`, `start_rtsp()` takes
two positional params:

    param1 = resolution : low | high | both   (anything else = use config value)
    param2 = audio      : no | yes | alaw | ulaw | pcm | aac

Exposed via the CGI at `/cgi-bin/service.sh`:

    http://CAM_IP/cgi-bin/service.sh?name=rtsp&action=stop
    http://CAM_IP/cgi-bin/service.sh?name=rtsp&action=start&param1=null&param2=null

Passing `null` leaves both at their configured values. Full reboot fallback:

    http://CAM_IP/cgi-bin/reboot.sh

## Incidental discovery: the cameras can run go2rtc themselves

`RTSP_ALT` accepts `standard`, `alternative`, or **`go2rtc`**. With `go2rtc`
selected the camera generates its own `/tmp/go2rtc.yaml` and can expose both
`ch0_0.h264` and `ch0_1.h264` via separate h264grabber processes.

That is a possible route around the "both RTSP streams not recommended"
constraint - it would give a real 640x360 substream for detection instead of
downscaling 1080p on the NVR. But it puts more load on the weakest component
in the system, which is already dropping its RTSP daemon.

Not now. Revisit only if NVR-side decode load turns out to be a problem, and
test on cam 5 first.
