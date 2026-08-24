# NVR setup - running Frigate on this PC

Target host is the local machine (Ryzen 5 3600X, 32 GB, RTX 4080 SUPER,
192.168.3.148) rather than the Beelink EQ14, which has not been bought.
Everything here ports to the EQ14 later - see "Porting" at the end.

## Current state of this machine

    WSL2            NOT installed
    Docker          NOT installed
    Hypervisor      present (virtualization is enabled in BIOS)
    NVIDIA driver   610.88, RTX 4080 SUPER 16 GB
    Free space      D: 559 GB   C: 254 GB

## Storage plan - 2 day retention

Measured main-stream bitrate: **1.19 Mbps** per camera.

    per camera / day   12.8 GB
    6 cameras / day     76.9 GB
    6 cameras x 2 days  154 GB continuous
    + alerts 14d and detections 7d, both motion-only (subsets)

Budget roughly 200 GB. Recordings go to `D:\frigate\media`, which is
`/mnt/d/frigate/media` inside WSL. D: has 559 GB free.

Write throughput is only ~0.9 MB/s aggregate, so the usual warning about slow
WSL access to Windows drives does not bite here - that penalty is about many
small operations, not sustained low-rate writes.

## Step 1 - install WSL2  (YOUR ACTION, needs admin + reboot)

In an **administrator** PowerShell:

    wsl --install -d Ubuntu

Then **reboot**. After reboot Ubuntu opens and asks for a UNIX username and
password. Any values are fine; note them down.

This is the only step that needs a reboot and it cannot be automated from here.

## Step 2 - Docker Engine + NVIDIA Container Toolkit inside WSL

Run `scripts/setup-wsl-docker.sh` from inside the Ubuntu shell, or paste its
contents. It installs Docker Engine, the compose plugin, and the NVIDIA
Container Toolkit, then verifies GPU passthrough.

## Step 3 - start the stack

    cd /mnt/d/Claude-BK/Frigate-Cams
    mkdir -p /mnt/d/frigate/media
    docker compose up -d
    docker compose logs -f frigate

Frigate UI: http://192.168.3.148:5000

Expect on first start:
- six cameras listed
- camera FPS around 20, detect FPS 5
- high CPU, because the CPU detector is doing all six cameras

## Step 4 - verify before leaving it running

    docker compose ps
    curl -s http://localhost:5000/api/stats | head -40
    ls -la /mnt/d/frigate/media/recordings

Check in the UI: live view on all six, recordings appearing, a person
detection firing.

## Step 5 - switch to the RTX 4080

Only after step 4 passes. The ONNX detector needs a model, and Frigate does
not ship one - it has to be exported.

    cd /mnt/d/Claude-BK/Frigate-Cams
    bash scripts/build-yolo-model.sh

That writes `services/nvr/config/model_cache/yolo.onnx`. Then in
`services/nvr/config/config.yml`:

1. comment out the `detectors: cpu1:` block
2. uncomment the `detectors: onnx:` and `model:` blocks
3. uncomment `hwaccel_args: preset-nvidia` under `ffmpeg:`

Then `docker compose restart frigate`. Inference time should drop to single-
digit milliseconds and CPU usage should collapse.

## Gotcha - NordVPN

NordLynx is active on this machine (10.5.0.2/16). If Docker or WSL cannot
reach 192.168.3.x, allow LAN traffic or split-tunnel in the Nord client.
Symptom: Frigate shows all six cameras offline while they respond fine to
curl from Windows.

## Image tag

`ghcr.io/blakeblackshear/frigate:stable-tensorrt`. I checked the registry -
the tensorrt variant is only published as `stable-tensorrt`, with no
per-version tag, so it cannot be pinned the way the plain image can. Note the
running version after first start (`docker compose logs frigate | head`) so a
future `docker compose pull` that breaks something can be identified.

## Porting to the EQ14 later

Only three edits:

1. `compose.yaml` - image `:stable-tensorrt` -> `:stable`, drop the whole
   `deploy:` GPU block, change `/mnt/d/frigate/media` to the real Linux path
2. `config.yml` - detector `onnx` -> `openvino` with `device: GPU`
3. `config.yml` - `hwaccel_args: preset-nvidia` -> `preset-vaapi`

Everything else - cameras, go2rtc, retention, snapshots - is unchanged.
