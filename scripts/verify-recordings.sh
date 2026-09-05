#!/bin/bash
# Decode the newest recorded segment for each camera end-to-end.
# Frames arriving is NOT the same as a playable recording - this checks playback.
#
# Uses ffprobe -count_frames, which fully decodes every frame WITHOUT a muxer.
# An output muxer would emit "non monotonically increasing dts" warnings caused
# by -use_wallclock_as_timestamps on the capture side; those are a test artifact
# and would mask the real signal. The corruption this guards against is the
# malformed AUD/filler NAL bug, which surfaces as "Invalid NAL unit size" or
# "Error splitting the input into NAL units" and as CHUNK_DEMUXER_ERROR in the UI.
FP=/usr/lib/ffmpeg/7.0/bin/ffprobe
rc=0
for cam in cam1_mensroom cam2_living cam3_kitchen cam4_hallway cam5_laundry cam6_extra; do
  f=$(find /mnt/d/frigate/media/recordings -path "*/$cam/*.mp4" -printf '%T@ %p\n' 2>/dev/null \
      | sort -n | tail -1 | cut -d' ' -f2-)
  if [ -z "$f" ]; then printf '%-16s NO SEGMENTS\n' "$cam"; rc=1; continue; fi
  cf="${f/\/mnt\/d\/frigate\/media//media/frigate}"
  out=$(docker exec frigate "$FP" -v error -select_streams v:0 -count_frames \
        -show_entries stream=nb_read_frames,width,height -of default=nw=1 "$cf" 2>&1)
  err=$(echo "$out" | grep -viE '^(nb_read_frames|width|height)=' | head -1)
  frames=$(echo "$out" | grep '^nb_read_frames=' | cut -d= -f2)
  dim=$(echo "$out" | grep -E '^(width|height)=' | cut -d= -f2 | paste -sd x -)
  sz=$(( $(stat -c%s "$f") / 1024 ))
  if [ -z "$err" ] && [ "${frames:-0}" -gt 0 ]; then
    printf '%-16s PLAYS OK    %5s frames  %-9s %5s KB\n' "$cam" "$frames" "$dim" "$sz"
  else
    printf '%-16s CORRUPT     %5s frames  %-9s %5s KB  %s\n' "$cam" "${frames:-0}" "$dim" "$sz" "${err:0:60}"
    rc=1
  fi
done
exit $rc
