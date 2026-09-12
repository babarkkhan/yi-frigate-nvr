#!/bin/bash
# Verify every go2rtc live-audio stream. Reads stream names from the live
# Frigate config so it cannot drift from what is actually deployed.
S=/mnt/d/Claude-BK/Frigate-Cams/scripts/verify-live-audio-any.py
streams=$(docker exec frigate python3 -c "
import yaml
print(' '.join(yaml.safe_load(open('/config/config.yml')).get('go2rtc',{}).get('streams',{})))" 2>/dev/null)
rc=0
for s in $streams; do
  dims=$(docker exec frigate python3 -c "
import yaml
d=yaml.safe_load(open('/config/config.yml'))['cameras']['$s']['detect']
print(d['width'], d['height'])" 2>/dev/null)
  out=$(docker exec -i frigate python3 - $s $dims < "$S" 2>&1)
  res=$(echo "$out" | grep -o '"RESULT": "[A-Z]*"' | cut -d'"' -f4)
  mp4=$(echo "$out" | grep '"fragmented_mp4"' | grep -o '"video_frames": "[0-9]*"' | cut -d'"' -f4)
  aac=$(echo "$out" | grep '"codec": "aac"' | grep -o '"rms_dbfs": [-0-9.]*' | sed 's/.*: //')
  opus=$(echo "$out" | grep '"codec": "opus"' | grep -o '"rms_dbfs": [-0-9.]*' | sed 's/.*: //')
  printf '  %-15s %-5s  video_frames=%-5s aac_rms=%-8s opus_rms=%-8s\n' \
    "$s" "${res:-ERR}" "${mp4:-0}" "${aac:-n/a}" "${opus:-n/a}"
  [ "$res" = "PASS" ] || rc=1
done
[ $rc -eq 0 ] && echo "  ALL STREAMS PASS" || echo "  ONE OR MORE STREAMS FAILED"
exit $rc
