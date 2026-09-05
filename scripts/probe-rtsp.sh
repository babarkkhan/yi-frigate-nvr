#!/bin/bash
# Probe each camera's RTSP stream and report whether it actually delivers video.
FF=/usr/lib/ffmpeg/7.0/bin/ffprobe
for spec in "cam1 192.168.3.5" "cam2 192.168.3.22" "cam3 192.168.3.3" \
            "cam4 192.168.3.4" "cam5 192.168.3.149" "cam6 192.168.3.6"; do
  set -- $spec
  name=$1; ip=$2
  out=$(timeout 25 docker exec frigate "$FF" -rtsp_transport tcp -timeout 12000000 \
        -v error -show_entries stream=codec_name,width,height \
        -of default=nw=1 "rtsp://$ip/ch0_0.h264" 2>&1 | tr '\n' ' ')
  rc=$?
  printf '%-6s %-15s rc=%-3s %s\n' "$name" "$ip" "$rc" "${out:0:90}"
done
