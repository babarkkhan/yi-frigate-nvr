#!/bin/bash
# Hammer one live-audio stream repeatedly and capture the failing diagnostics.
# For the pilot's open item: intermittent audio failure on open/reconnect.
S=/mnt/d/Claude-BK/Frigate-Cams/scripts/verify-live-audio-any.py
stream=${1:-cam4_hallway}; n=${2:-5}
pass=0; fail=0
for i in $(seq 1 "$n"); do
  out=$(docker exec -i frigate python3 - "$stream" 1920 1088 < "$S" 2>&1)
  res=$(echo "$out" | grep -o '"RESULT": "[A-Z]*"' | cut -d'"' -f4)
  if [ "$res" = "PASS" ]; then
    pass=$((pass+1)); echo "  run $i: PASS"
  else
    fail=$((fail+1)); echo "  run $i: FAIL"
    echo "$out" | grep -v '"RESULT"' | while read -r l; do
      c=$(echo "$l" | grep -o '"codec": "[a-z]*"' | cut -d'"' -f4)
      o=$(echo "$l" | grep -o '"ok": [a-z]*' | sed 's/.*: //')
      t=$(echo "$l" | grep -o '"tail": "[^"]*"' | cut -d'"' -f4)
      e=$(echo "$l" | grep -o '"error": "[^"]*"' | cut -d'"' -f4)
      d=$(echo "$l" | grep -o '"decoded_seconds": [0-9.]*' | sed 's/.*: //')
      printf '      %-6s ok=%-6s decoded=%-8s %s%s\n' "${c:-mp4}" "$o" "${d:-}" "$t" "$e"
    done
  fi
done
echo "  --> $stream: $pass pass / $fail fail of $n"
