#!/bin/bash
# Verify every go2rtc live-audio stream declared in the LIVE Frigate config.
#
# FAILURE PROPAGATION. An earlier version of this script had a real bug, caught
# in review of the cam3 pilot: if the stream list came back empty - docker exec
# failing, unreadable YAML, a missing go2rtc block - the loop body never ran,
# rc stayed 0, and it printed "ALL STREAMS PASS" and exited 0. A check that
# reports success without having checked anything is worse than no check.
#
# It now fails closed: an empty or unreadable stream list is an error, a stream
# with no matching camera key is an error rather than silently falling back to
# default dimensions, and an unparseable verifier result is an error. Optionally
# pass the number of streams you EXPECT as $1 to assert the count as well.
set -uo pipefail

S="$(dirname "$(readlink -f "$0")")/verify-live-audio-any.py"
expect=${1:-}
rc=0

[ -r "$S" ] || { echo "FATAL: verifier not readable at $S"; exit 2; }

streams=$(docker exec frigate python3 -c "
import yaml
print(' '.join(yaml.safe_load(open('/config/config.yml')).get('go2rtc',{}).get('streams',{})))" 2>/dev/null)

if [ -z "${streams// /}" ]; then
  echo "FATAL: no go2rtc streams found in the live config."
  echo "  Either none are configured, or reading the config failed."
  echo "  NOT reporting success - this is the empty-list trap."
  exit 2
fi

count=$(echo "$streams" | wc -w)
if [ -n "$expect" ] && [ "$count" -ne "$expect" ]; then
  echo "FATAL: expected $expect streams, live config declares $count ($streams)"
  exit 2
fi
echo "verifying $count stream(s): $streams"

for s in $streams; do
  dims=$(docker exec frigate python3 -c "
import yaml,sys
c=yaml.safe_load(open('/config/config.yml')).get('cameras',{}).get('$s')
if not c: sys.exit(3)
d=c['detect']; print(d['width'], d['height'])" 2>/dev/null)
  if [ -z "$dims" ]; then
    printf '  %-15s ERROR  no matching camera key - cannot determine dimensions\n' "$s"
    rc=1; continue
  fi

  command_rc=0
  out=$(docker exec -i frigate python3 - "$s" $dims < "$S" 2>&1) || command_rc=$?
  res=$(echo "$out" | grep -o '"RESULT": "[A-Z]*"' | cut -d'"' -f4)
  mp4=$(echo "$out" | grep '"fragmented_mp4"' | grep -o '"video_frames": "[0-9]*"' | cut -d'"' -f4)
  aac=$(echo "$out" | grep '"codec": "aac"' | grep -o '"rms_dbfs": [-0-9.]*' | sed 's/.*: //')
  opus=$(echo "$out" | grep '"codec": "opus"' | grep -o '"rms_dbfs": [-0-9.]*' | sed 's/.*: //')

  if [ -z "$res" ]; then
    printf '  %-15s ERROR  verifier produced no RESULT line\n' "$s"
    echo "$out" | tail -3 | sed 's/^/        /'
    rc=1; continue
  fi
  printf '  %-15s %-5s  dims=%-9s video_frames=%-5s aac_rms=%-8s opus_rms=%-8s\n' \
    "$s" "$res" "${dims// /x}" "${mp4:-0}" "${aac:-n/a}" "${opus:-n/a}"
  if [ "$res" != "PASS" ] || [ "$command_rc" -ne 0 ]; then
    echo "$out"
    rc=1
  fi
done

if [ $rc -eq 0 ]; then
  echo "ALL $count STREAMS PASS"
else
  echo "ONE OR MORE STREAMS FAILED"
fi
exit $rc
