#!/bin/bash
# Newest recorded segment per camera - shows how long a camera has been down.
echo "now: $(date '+%Y-%m-%d %H:%M:%S')"
for c in cam1_mensroom cam2_living cam3_kitchen cam4_hallway cam5_laundry cam6_extra; do
  t=$(find /mnt/d/frigate/media/recordings -path "*/$c/*.mp4" -printf '%T@\n' 2>/dev/null | sort -n | tail -1)
  if [ -z "$t" ]; then printf '  %-16s no segments\n' "$c"; continue; fi
  age=$(awk "BEGIN{printf \"%.0f\", $(date +%s) - $t}")
  printf '  %-16s last %s   (%s min ago)\n' "$c" \
    "$(date -d "@${t%.*}" '+%Y-%m-%d %H:%M:%S')" "$((age/60))"
done
