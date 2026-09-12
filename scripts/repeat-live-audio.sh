#!/bin/bash
# Hammer one live-audio stream repeatedly and capture failing diagnostics.
# For the open item: intermittent audio failure on open/reconnect.
#
#   repeat-live-audio.sh <stream> [runs]
#
# Dimensions are read from the LIVE Frigate config, not hardcoded. An earlier
# version assumed 1920x1088, which is wrong for the Allwinner cameras
# (1920x1080) and would have reported false failures for them.
set -uo pipefail
S=/mnt/d/Claude-BK/Frigate-Cams/scripts/verify-live-audio-any.py
stream=${1:-cam5_laundry}; n=${2:-5}

dims=$(docker exec frigate python3 -c "
import yaml,sys
c=yaml.safe_load(open('/config/config.yml')).get('cameras',{}).get('$stream')
if not c: sys.exit(3)
d=c['detect']; print(d['width'], d['height'])" 2>/dev/null)
if [ -z "$dims" ]; then
  echo "FATAL: no camera key '$stream' in the live config - cannot get dimensions"
  exit 2
fi
echo "hammering $stream at ${dims// /x}, $n runs"

pass=0; fail=0
declare -A codecfail
for i in $(seq 1 "$n"); do
  out=$(docker exec -i frigate python3 - "$stream" $dims < "$S" 2>&1)
  res=$(echo "$out" | grep -o '"RESULT": "[A-Z]*"' | cut -d'"' -f4)
  if [ "$res" = "PASS" ]; then
    pass=$((pass+1)); echo "  run $i: PASS"
  else
    fail=$((fail+1)); echo "  run $i: ${res:-NO-RESULT}"
    while IFS= read -r l; do
      echo "$l" | grep -q '"ok": false' || continue
      c=$(echo "$l" | grep -o '"codec": "[a-z]*"' | cut -d'"' -f4)
      c=${c:-fragmented_mp4}
      codecfail[$c]=$(( ${codecfail[$c]:-0} + 1 ))
      d=$(echo "$l" | grep -o '"decoded_seconds": [0-9.]*' | sed 's/.*: //')
      t=$(echo "$l" | grep -o '"tail": "[^"]*"' | cut -d'"' -f4)
      e=$(echo "$l" | grep -o '"error": "[^"]*"' | cut -d'"' -f4)
      printf '      %-16s decoded=%-8s %s%s\n' "$c" "${d:-n/a}" "$t" "$e"
    done <<< "$out"
  fi
done
echo "  --> $stream: $pass pass / $fail fail of $n"
for c in "${!codecfail[@]}"; do echo "      failures by component: $c = ${codecfail[$c]}"; done
[ "$fail" -eq 0 ]
