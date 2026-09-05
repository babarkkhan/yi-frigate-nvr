#!/bin/bash
# Show recorded footage per day, to confirm retention is actually pruning.
# continuous: 2 days, alerts: 14 days, detections: 7 days - so days older than
# 2 SHOULD still exist, but hold only event-associated segments and be small.
cd /mnt/d/frigate/media/recordings || exit 1
printf '%-12s %8s %8s\n' DAY SIZE SEGMENTS
for d in */; do
  d=${d%/}
  printf '%-12s %8s %8s\n' "$d" "$(du -sh "$d" 2>/dev/null | cut -f1)" "$(find "$d" -name '*.mp4' | wc -l)"
done
printf '%-12s %8s\n' TOTAL "$(du -sh . 2>/dev/null | cut -f1)"
