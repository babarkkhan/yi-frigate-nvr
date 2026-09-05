#!/bin/bash
# Reproduce upstream yi-hack-MStar issue #593: does muxing rtsp_server_yi's
# stream into MP4 still produce NAL errors, and are AUD/filler units present?
CAM=${1:-192.168.3.22}
FF=/usr/lib/ffmpeg/7.0/bin/ffmpeg
FP=/usr/lib/ffmpeg/7.0/bin/ffprobe

echo "=== 1. mux RTSP -> MP4, NO bitstream filter (original repro) ==="
docker exec frigate "$FF" -hide_banner -loglevel error -rtsp_transport tcp \
  -i "rtsp://$CAM/ch0_0.h264" -t 20 -an -c copy -y /tmp/nofilter.mp4 2>&1 \
  | grep -viE "non monotonic" | tail -5
echo "(mux done)"

echo
echo "=== 2. ffprobe full decode of that MP4 - errors are the bug signature ==="
docker exec frigate "$FP" -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames -of default=nw=1 /tmp/nofilter.mp4 2>&1 | head -25

echo
echo "=== 3. NAL census of the muxed MP4, converted back to Annex-B ==="
docker exec frigate "$FF" -hide_banner -loglevel error -i /tmp/nofilter.mp4 \
  -c copy -bsf:v h264_mp4toannexb -f h264 -y /tmp/back.h264 2>&1 | tail -2
docker exec frigate python3 /tmp/na.py /tmp/back.h264 2>&1 | head -14
