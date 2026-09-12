#!/bin/bash
# Coordinated recovery/redeploy using cached, pinned images. Brief recording gap.
# Default is read-only preflight; --apply recreates Frigate, then Tailscale.
# Does not reboot cameras/Windows/WSL, change retention or pull new images.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir/.."
case "${1:---check}" in
  --check|--apply) mode="${1:---check}" ;;
  *) echo 'Usage: bash scripts/restart-nvr.sh [--check|--apply]' >&2; exit 2 ;;
esac
compose=(docker compose -f compose.yaml -f compose.tailscale.yaml)
"${compose[@]}" config --quiet
images=$("${compose[@]}" config --images)
[[ -n "$images" ]] || { echo 'ERROR: no images in Compose config' >&2; exit 2; }
while IFS= read -r image; do
  [[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || { echo 'ERROR: unpinned image' >&2; exit 2; }
  docker image inspect "$image" --format '{{.Id}}' >/dev/null
done <<< "$images"
echo 'Preflight: Compose valid; all pinned images present locally.'
if [[ "$mode" == --check ]]; then
  bash "$script_dir/nvr-status.sh"
  exit $?
fi
exec 9>/tmp/home-nvr-restart.lock
flock -n 9 || { echo 'ERROR: another NVR restart is running' >&2; exit 2; }
trap 'echo "ERROR: recovery stopped at line $LINENO; inspect container health before retrying. Tailscale may be stopped." >&2' ERR
echo 'Stopping Tailscale before replacing its shared network namespace.'
"${compose[@]}" stop -t 20 tailscale
"${compose[@]}" up -d --no-deps --force-recreate --pull never --wait --wait-timeout 150 frigate
"${compose[@]}" up -d --no-deps --force-recreate --pull never --wait --wait-timeout 120 tailscale
docker exec tailscale wget -qO- http://127.0.0.1:5000/api/version
echo
echo 'Containers ready and shared-namespace HTTP responds. Check remote tailnet access separately.'
trap - ERR
# Allow a first segment to finalize. Do not restart working containers merely
# because one camera is offline; report that condition separately.
sleep 20
if ! bash "$script_dir/nvr-status.sh"; then
  echo 'ERROR: containers recovered, but one or more cameras/recordings are unhealthy.' >&2
  exit 1
fi
