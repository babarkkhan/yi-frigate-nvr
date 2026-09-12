#!/bin/bash
# Probe audio track + timestamp pacing on every MStar camera.
# See scripts/probe-camera-audio.py for how to read the ratio.
S=/mnt/d/Claude-BK/Frigate-Cams/scripts/probe-camera-audio.py
printf '%-15s %-11s %-7s %-9s %-9s %-7s %-10s %s\n' CAMERA CODEC RATE REQ_S DECODED RATIO ASETPTS RMS_dBFS
for c in "192.168.3.5 cam1_mensroom" "192.168.3.22 cam2_living" \
         "192.168.3.4 cam4_hallway" "192.168.3.149 cam5_laundry"; do
  set -- $c
  j=$(docker exec -i frigate python3 - "$1" "$2" < "$S" 2>/dev/null)
  g() { echo "$j" | grep -o "\"$1\": [^,]*" | head -1 | sed 's/.*: //; s/"//g'; }
  printf '%-15s %-11s %-7s %-9s %-9s %-7s %-10s %s\n' \
    "$2" "$(g audio_codec)" "$(g sample_rate)" "$(g requested_seconds)" \
    "$(g decoded_seconds)" "$(g decoded_per_requested)" "$(g needs_asetpts)" "$(g rms_dbfs)"
done
