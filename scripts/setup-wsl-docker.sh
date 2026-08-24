#!/usr/bin/env bash
# Run INSIDE the WSL Ubuntu shell, after `wsl --install -d Ubuntu` and a reboot.
# Installs Docker Engine, the compose plugin, and the NVIDIA Container Toolkit.
set -euo pipefail

echo "==> checking we are in WSL"
grep -qi microsoft /proc/version || { echo "This is not WSL. Aborting."; exit 1; }

echo "==> base packages"
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg jq

echo "==> docker apt repo"
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

echo "==> docker engine + compose"
sudo apt-get update -qq
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER"

echo "==> nvidia container toolkit"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update -qq
sudo apt-get install -y -qq nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker

echo "==> starting docker"
sudo systemctl enable --now docker
sudo systemctl restart docker   # required: nvidia-ctk just rewrote /etc/docker/daemon.json
sleep 3

echo "==> media directory"
mkdir -p /mnt/d/frigate/media

echo
echo "==> verification"
sudo docker version --format '  docker server: {{.Server.Version}}'
sudo docker compose version | sed 's/^/  /'
echo "  --- GPU passthrough test ---"
if sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi \
     --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null; then
  echo "  GPU OK"
else
  echo "  GPU test FAILED - Frigate will still run on CPU."
  echo "  Comment out the deploy: block in compose.yaml if it blocks startup."
fi

echo
echo "Done. Run 'wsl --shutdown' from Windows, then reopen WSL, so the docker group applies."
echo "Then:  cd /mnt/d/Claude-BK/Frigate-Cams && docker compose up -d"
