#!/bin/bash
# One-shot NVR health summary: per-camera fps, detector speed, GPU, uptime.
docker exec frigate bash -c 'curl -s --max-time 20 http://127.0.0.1:5000/api/stats > /tmp/s.json && python3 - <<PY
import json
d = json.load(open("/tmp/s.json"))
bad = []
print("%-16s %8s %8s %8s" % ("CAMERA", "FPS", "DETECT", "SKIP"))
for k, v in sorted(d.get("cameras", {}).items()):
    fps = v.get("camera_fps", 0)
    if fps < 1: bad.append(k)
    print("%-16s %8.1f %8.1f %8.1f" % (k, fps, v.get("detection_fps",0), v.get("skipped_fps",0)))
print()
for k, v in d.get("detectors", {}).items():
    print("detector %-8s inference %s ms" % (k, v.get("inference_speed")))
for k, v in d.get("gpu_usages", {}).items():
    print("gpu %s -> %s" % (k, v))
s = d.get("service", {})
print("frigate %s   uptime %ss" % (s.get("version"), s.get("uptime")))
print("STATUS:", "ALL OK" if not bad else "NO FRAMES: " + ", ".join(bad))
PY'
