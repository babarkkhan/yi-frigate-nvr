#!/bin/bash
# What tracks does each camera's newest recording actually contain?
# Enabling PCM on the Allwinner cameras also gives their RECORDINGS an audio
# track, since Frigate's record args already transcode audio to AAC.
FP=/usr/lib/ffmpeg/7.0/bin/ffprobe
for c in cam1_mensroom cam2_living cam3_kitchen cam4_hallway cam5_laundry cam6_extra; do
  f=$(find /mnt/d/frigate/media/recordings -path "*/$c/*.mp4" -printf '%T@ %p\n' 2>/dev/null \
      | sort -n | tail -1 | cut -d' ' -f2-)
  if [ -z "$f" ]; then printf '  %-15s no segments\n' "$c"; continue; fi
  cf="${f/\/mnt\/d\/frigate\/media//media/frigate}"
  tracks=$(docker exec frigate "$FP" -v error \
           -show_entries stream=codec_type,codec_name,sample_rate \
           -of csv=p=0 "$cf" 2>/dev/null | paste -sd'   ' -)
  printf '  %-15s %s\n' "$c" "$tracks"
done
