#!/bin/bash
# Local check only. Invoking via WSL can start WSL and mask an availability fault.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
docker exec -i frigate python3 - < "$script_dir/check-nvr.py"
