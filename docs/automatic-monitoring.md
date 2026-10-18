# Automatic outage detection and bounded recovery

Implementation prepared October 18, 2026. This supersedes the earlier design
review where it differs. No AI session is required to run these components.

## Deployment status

- The independent Hetzner `nvr-monitor.timer` is enabled. It checks the five
  required cameras through the authenticated private gateway and checks the
  public HTTPS authentication redirect.
- The restricted Windows-to-VPS heartbeat was delivered successfully during
  commissioning. Its dedicated SSH key cannot open a shell, forward ports or
  write arbitrary paths; it can submit only a bounded health JSON object.
- The native Windows watchdog is installed as `HomeNVR-Health-Recovery` with
  startup and minute triggers. After UAC approval, commissioning passed under
  the actual S4U task account at 21:16 Riyadh on October 18: native camera health,
  restricted SSH heartbeat delivery and read-only WSL diagnosis all succeeded.
  Automatic recovery is enabled. The VPS independently received subsequent
  scheduled heartbeats and confirmed all five required cameras recording.
- A controlled cam2 stream-service failure was detected by both monitors. After
  the lock fix described below, the scheduled task requested a targeted cam2
  restart at 21:29 Riyadh, capture resumed at about 5 FPS, and fresh H.264/AAC
  recordings from all five active cameras decoded without reported errors.
- Notification delivery is **not configured**. The owner dropped alert setup
  from the current scope on October 18. No test notification was sent.
- The router reservation is **not saved**. The owner also dropped router edits
  from the current scope. The PC remains on its existing DHCP lease; its address
  and adapter MAC are retained privately, not published here.
- Cam6 is explicitly excluded as intentionally unplugged. Add it to both
  monitors' `expected` lists when it returns to service; do not infer maintenance
  from a failed feed.

Independent health observation remains enabled without notification delivery.
Do not describe alerts or DHCP reservation as completed.

## Architecture

`scripts/nvr-monitor.py` runs natively on Windows, once a minute, under the WSL
owner's scheduled-task account. Before invoking WSL it checks Frigate FPS,
nonempty recording file freshness, free disk space and the NVR's LAN address.
It searches the current and preceding UTC recording hour. Missing files,
missing/invalid FPS, stale/future timestamps and API failure fail closed.
Healthy routine observations never invoke WSL.

The Windows controller sends a small status heartbeat using a dedicated SSH key.
The VPS forced command `receive-nvr-heartbeat.py` validates its schema, size and
timestamp and atomically stores it. The monitor reads this alongside independent
camera checks. A heartbeat older than four minutes is a failure, so a stopped
watchdog is detectable even if the camera server still runs. No footage,
microphone audio, credentials or full camera configuration is sent.

The independent service runs each calendar minute. Long checks do not overlap;
the next calendar tick remains scheduled. Three consecutive failed observations
produce an outage event; three healthy observations produce a recovery event.
Delivery happens on these transitions, with five-minute retries if sending
fails. A provider accepting a message is not proof the recipient read it.
Actual alert delay depends on check duration and failure type; a missing
heartbeat must first exceed its four-minute threshold.

The VPS can detect failure of the home PC, LAN, internet, gateway, or local
watchdog. It cannot independently alert about its own complete failure without
a third-party monitor. Capture/freshness checks do not continuously decode every
recording or exercise a phone's microphone/playback session.

## Recovery policy

Windows records a snapshot and persistent attempt budget before acting. Both
Windows and WSL re-read health before selecting a repair. A named local state
file is protected by an OS file lock; scheduled task instances also do not
overlap. The WSL worker shares the existing manual recovery lock.

| Evidence | Permitted automatic action |
|---|---|
| All required cameras fail and the WSL GPU probe fails | Stop NVR containers; terminate only the configured Ubuntu distro; verify GPU access; use the pinned coordinated container recovery helper |
| NVR container unavailable | Start Docker if needed and use the existing coordinated pinned-image recovery helper |
| Camera SSH reachable but RTSP protocol unresponsive | Use verified camera admin keys in process memory to stop its RTSP/watchdog, stop old grabbers, then start its configured stream service |
| All required recording/capture checks fail while GPU and all camera RTSP services respond | One coordinated NVR recovery |
| API unavailable while recording files advance | Alert; do not interrupt recording |
| Unreachable individual camera, low disk, changed LAN address, or ambiguous fault | Alert; no speculative whole-stack restart, deletion, or network reconfiguration |

There is a 15-minute cooldown, at most two attempts per hour, and at most two
attempts per incident. Budgets survive process and WSL restarts. Three healthy
observations end the incident; a command's successful exit alone does not.
An offline/ambiguous classification may consume a diagnostic attempt without
performing a repair. Unresolved faults remain visible for operator intervention.

The controller never reboots Windows, terminates other WSL distributions,
updates firmware, pulls new container versions, widens SSH access, deletes
recordings or changes retention. A WSL reset is explicitly enabled only in the
private deployment configuration. If GPU access remains broken afterward, it
does not escalate to a global WSL shutdown or a Windows reboot.

## Commissioning and operation

The Windows installer creates `HomeNVR-Health-Recovery` with startup and minute
triggers, S4U under the WSL owner, highest run level, and IgnoreNew. It first
disables recovery and requests commissioning. Under the actual task account,
the controller must pass native camera health, heartbeat delivery and a
read-only WSL diagnosis. Only then does it enable recovery and persist
`commissioned_at`. Failed commissioning leaves recovery disabled.

Keep the native Python runtime in the private ignored deployment runtime folder;
the task does not depend on a running Codex app. Keep the JSON configuration and
heartbeat key protected with Windows ACLs. VPS configuration is root-readable
only. Templates are `secrets/nvr-monitor.example` and `secrets/nvr-alerts.example`.

Telegram or authenticated STARTTLS SMTP delivery is supported by the current
implementation. Set the approved destination privately, run the VPS monitor
with `--test-notification`, and obtain recipient confirmation. Then test a
missing heartbeat and recovery with the camera recording pipeline left running.
Do not publish bot tokens, SMTP passwords or recipient details.

Before relying on automatic recovery, exercise a controlled camera-service
failure under the actual task, confirm the bounded targeted recovery and
advancing decodable recordings, and check a planned Windows reboot. Unit tests
cover classification and limits, but do not replace these deployment tests.

State is one atomic `state.json`, `last-run.json`, and at most 30
`recovery-*.json` snapshots per controller. To pause for maintenance, place
`{"until": UNIX_UTC_EXPIRY}` in `maintenance.json` in **both** state directories.
The pause expires automatically. Retain both copies because pausing only Windows
would otherwise look like a missing heartbeat from the VPS.

For the DHCP reservation, use the router's DHCP/address-reservation page to bind
the verified Ethernet MAC to its current address. Verify the saved entry, then
confirm the PC retains that address on a later lease renewal. Do not force a
lease release during remote operation. A Windows static IP alone is not a router
reservation and can collide with the DHCP pool.

## Validation performed during preparation

Nineteen native Python fixtures passed (including six existing NVR checks):
failure/recovery debounce, delivery retention, durable cooldown/attempt caps,
cross-process exclusion, date boundaries, stale/missing recordings, invalid FPS,
WSL-free observation, and safe recovery classification. Live native observation
passed for all five required cameras. A dedicated heartbeat reached the VPS,
and the independent five-camera check passed. The timer unit validated and ran.
The Linux-specific recovery-lock regression also passed in WSL. The first live
camera failure exercise exposed Linux `protected_regular` rejecting the root
worker's write/create open of a lock owned by the manual operator. The worker
and coordinated restart helper now lock a read-only descriptor without
truncating the shared file. Cross-process exclusion and acquisition by root
against the existing operator-owned lock were verified.
Windows task registration, scheduled-account commissioning and the corrected
targeted camera-recovery path passed live checks. The failed first exercise was
restored manually. Its cooldown was explicitly waived once for the repeat
exercise; permanent debounce, cooldown and retry limits were unchanged, and
both attempts' evidence was retained privately.
Three consecutive healthy scheduled observations confirmed recovery by 21:32
Riyadh. The two deliberate commissioning attempts were then archived and removed
from the production repair budget so they would not block a genuine incident;
the configured limits remain unchanged.

A planned Windows reboot, actual GPU-reset recovery and whole-stack failure
recovery have not been exercised under the new watchdog. Passing the targeted
camera test does not establish those paths. Alerts and router changes were
subsequently removed from scope by the owner.
