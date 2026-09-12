# Disconnect investigation, recovery and storage — 2026-09-12

## Findings and limits

Cam4 and cam5's intermittent faults are real, but their root cause is still
unresolved. Do not relabel a passing retry as a permanent fix, or assume that
all camera failures share a cause. No camera firmware, audio settings, stream
selection or recording arguments were changed during this investigation.

| Observation | Evidence | Interpretation |
|---|---|---|
| Cam4 recording interruption | Recording index has a 14.6 s gap from 13:49:21 to 13:49:36 UTC. Prior logs show the input ended, FFmpeg restarted, and RTSP connections were refused. One boundary segment decoded only 69 video frames with an H.264 macroblock error. | Genuine lost recording coverage, beyond a playback-only problem. |
| Cam4 did not fully reboot around that incident | At 13:56–14:01 UTC its status reported about 97,000 s uptime; at 19:02 UTC uptime was about 115,300 s. | Points toward RTSP/service disruption rather than a whole-camera reboot; a specific daemon bug or load cause has not been isolated. |
| Cam5 live producer ended | Earlier go2rtc EOF and partial Opus capture; isolated retry passed. Its uptime likewise continued across the event. | A lost live source, not proof of an audio codec fault or camera reboot. |
| Healthy short baseline | Thirteen samples over two minutes: all six had frames, fresh indexed recordings, and one established camera RTSP connection each. No sampled uptime reset. | Recording-only baseline; it does not stress concurrent viewing. |
| Targeted live retry | Later cam4 and cam5 data-saver MP4 samples both fully decoded video/AAC at about 0.458 Mbps. | Failure was not reproduced by this short pair test. The test occurred after the baseline, not concurrently with it. |
| Cam4 HTTP status timed out once while video continued | At 19:02:26 UTC the status CGI failed, capture still reported 5.7 fps and subsequent status/uptime recovered. | An HTTP-only camera check would give misleading results. |
| Cam6 unavailable later | Last recording at 18:36:49 UTC; no RTSP connection, HTTP unreachable, Windows ping timed out and Frigate logged `No route to host`. Owner confirmed it had been unplugged and plugged it back in. | Intentional power-off, not evidence of a new software defect. All six subsequently passed the frame/freshness check. |

The index also contains a common approximately 33 s gap on all six cameras
around 18:26 UTC. The Frigate container start time did not change. This is a
separate unclassified common event; the evidence does not identify its cause.
Do not count the owner's later cam6 power-off as its explanation.

The earlier deployment restart produced 42–51 s index gaps around 13:48 UTC;
these are maintenance interruptions and must be separated from camera faults.
Index gaps measure missing indexed coverage, not exact human-visible playback
loss. A complete corruption inventory would require decoding every segment.

## Changes implemented

### Reproducible images

Compose pins the exact images already installed, without upgrading:

- Frigate 0.17.2 TensorRT:
  `ghcr.io/blakeblackshear/frigate@sha256:8a364092b03561b9c08ac00730206e363a53d07ea0304f7d543b403b65432b5e`
- Tailscale 1.102.3:
  `tailscale/tailscale@sha256:8c42c4574ab066384fcb72f69e086a2ff1dd3652eb6f56856cee34bcf0d2f680`

These are the observed deployment image digests, not a promise of portability
to other CPU architectures or automatic security updates. Upgrade deliberately,
test, then replace the digest. The recovery helper refuses mutable tags or
missing local images and uses `--pull never`.

### Coordinated recovery

`depends_on.frigate.restart: true` tells Compose to restart Tailscale after an
explicit Compose operation affecting Frigate. It does not apply to a raw
`docker restart frigate` or automatically supervise crash/unhealthy states.

Use the new helper from the deployment checkout in WSL:

```sh
bash scripts/restart-nvr.sh --check  # read-only preflight and local health
bash scripts/restart-nvr.sh --apply # brief recording interruption
```

Apply validates configuration and cached pins, takes an exclusive restart lock,
stops Tailscale, recreates Frigate and waits for health, then recreates Tailscale
against the new shared namespace and waits for its health. It checks HTTP from
inside the sidecar and then verifies camera frames and fresh recording-index
timestamps. Frigate failure prevents sidecar startup; errors are reported with
nonzero status. An offline camera is reported separately after container
recovery and does not trigger repeated restarts of healthy services.

Verify `http://home-nvr:5000` from a tailnet client afterward: the in-container
HTTP check is not an end-to-end remote test. The helper does not automatically
reboot Windows, WSL or cameras. If Frigate fails during recreation, Tailscale
may remain stopped: inspect the failure and rerun after fixing it.

The existing Windows keepalive already has startup plus five-minute triggers,
IgnoreNew, no execution time limit, and was Running. Docker is enabled under
systemd. These correct settings were preserved. Unattended unhealthy-container
recovery, stale NVIDIA/WSL driver mounts and external outage notification remain
separate work; this change does not claim to solve them.

### Checks that fail closed

`scripts/nvr-status.sh` now delegates to `check-nvr.py`. Missing expected camera
stats, invalid/zero FPS, and missing/stale recording timestamps produce failure.
An empty configuration cannot print success. Explicitly disabled cameras and
recording switches are respected. This is a local check; invoking it through
WSL may start WSL and conceal an availability outage. It is not an independent
monitor, and an indexed segment is not proof of decodable media.

## Storage measurements

The temporary-file test wrote 64 MiB per location in 4 MiB chunks, flushing each
chunk with fsync, then measured 32 small create/flush/rename/delete operations.
The test removed only its own unique temporary files. Recording continued.

| Location | Write + fsync MiB/s | Median / max per 4 MiB (ms) | Median metadata operation (ms) |
|---|---:|---:|---:|
| `/media/frigate` — Windows recording mount | 121.76 | 32.26 / 36.62 | 11.44 |
| `/config` — Windows configuration mount | 97.58 | 33.76 / 134.32 | 13.93 |
| `/tmp` — Linux container writable layer | 264.82 | 13.19 / 26.54 | 4.81 |

This is a small application-I/O sample, not a saturated/raw disk benchmark.
It cannot certify sustained performance, durability across the host's storage
stack or behavior under full-disk pressure. Warm reads were cached and should
not be used as physical disk throughput. The Linux comparison uses Docker's
writable layer, not a dedicated bare filesystem benchmark.

The recording mount has substantial headroom in this sample; there is no
evidence here that sustained storage bandwidth caused the observed camera RTSP
refusals. Config/metadata operations are slower on the Windows mount. A future
controlled trial moving database/config state to Linux-native storage is more
justified than immediately moving the entire media archive. Back up and test
database restore and Windows access needs before such a migration.

## Reusable evidence collection

```sh
# Run inside the deployment checkout. Output is operational JSONL, not secrets.
docker exec -i frigate python3 - --seconds 120 < scripts/observe-camera-disconnects.py
docker exec -i frigate python3 - < scripts/measure-storage.py
```

The observer opens no camera RTSP sessions. It samples selected HTTP fields,
Frigate frame rates, recording-index freshness and established RTSP TCP sockets
visible in Frigate's namespace. Other clients are not counted. It does not
capture Wi-Fi/AP events, camera process lists or packet traces. Correlate its
UTC timestamps with Frigate/go2rtc logs and operator actions during the next
failure before choosing a camera daemon restart, firmware change, or upstream
connection consolidation. Raw camera status/config dumps and media stay private.

## Validation

Twenty-one tests passed, including missing/stale camera data, non-finite FPS,
preflight-only behavior, missing pins, failed Frigate startup and correct
sidecar restart ordering. Shell syntax checks passed. The live helper completed
successfully: Frigate started at 19:08:46 UTC, then Tailscale at 19:09:06 UTC,
both healthy and using the exact pinned image IDs. The existing tailnet hostname
responded from the Windows host afterward. An off-LAN phone test was not run.

The controlled restart produced 43–52 s recording-index gaps. Afterward, fresh
full-resolution H.264 and AAC recordings on all six decoded without errors;
sample ages were 23–32 s. All twelve live stream definitions and both ordered
choices per camera remained loaded. These are short acceptance checks, not a
long-duration soak or proof that the earlier camera disconnects are fixed.

The first deployment preflight caught a malformed YAML comment introduced
during text replacement. It was corrected and preflight passed before any
container was stopped. The invalid configuration never reached a container.

## Sources

- [Docker Compose dependency startup and restart behavior](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker restart-policy limitations](https://docs.docker.com/engine/containers/start-containers-automatically/)
- [Earlier setup and data-saver review](setup-review-and-data-saver.md)
