#!/bin/bash
# Which part of the workaround actually fixes upstream #593?
# If removing a NON-EXISTENT NAL type also fixes it, then the cure is
# filter_units re-serialising the bitstream, not the removal of any type.
CAM=${1:-192.168.3.22}
FF=/usr/lib/ffmpeg/7.0/bin/ffmpeg
FP=/usr/lib/ffmpeg/7.0/bin/ffprobe

docker exec frigate "$FF" -hide_banner -loglevel error -rtsp_transport tcp \
  -i "rtsp://$CAM/ch0_0.h264" -t 20 -an -c copy -y /tmp/src.mp4 2>/dev/null

try() { # label  bsf-args...
  label=$1; shift
  if [ "$1" = "NONE" ]; then
    docker exec frigate "$FF" -hide_banner -loglevel error -i /tmp/src.mp4 \
      -c copy -y /tmp/t.mp4 2>/dev/null
  else
    docker exec frigate "$FF" -hide_banner -loglevel error -i /tmp/src.mp4 \
      -c copy -bsf:v "$1" -y /tmp/t.mp4 2>/dev/null
  fi
  errs=$(docker exec frigate "$FP" -v error -count_frames -select_streams v:0 \
         -show_entries stream=nb_read_frames -of default=nw=1 /tmp/t.mp4 2>&1 \
         | grep -c "Invalid NAL unit size")
  frames=$(docker exec frigate "$FP" -v error -count_frames -select_streams v:0 \
         -show_entries stream=nb_read_frames -of default=nw=1 /tmp/t.mp4 2>&1 \
         | grep "^nb_read_frames=" | cut -d= -f2)
  printf '  %-42s NAL-errors=%-5s frames=%s\n' "$label" "$errs" "${frames:-?}"
}

echo "=== ablation on $CAM ==="
try "no filter (baseline)"                    NONE
try "filter_units=remove_types=9|12 (mine)"   "filter_units=remove_types=9|12"
try "filter_units=remove_types=99 (NO-OP)"    "filter_units=remove_types=99"
try "filter_units=remove_types=6 (SEI only)"  "filter_units=remove_types=6"
try "h264_metadata (pure re-serialise)"       "h264_metadata"
