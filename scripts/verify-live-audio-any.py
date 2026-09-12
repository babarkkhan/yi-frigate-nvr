#!/usr/bin/env python3
"""Verify a go2rtc live-audio stream for ANY camera.

  docker exec -i frigate python3 - <stream> <width> <height> < this

Generalised from scripts/verify-live-audio.py, which is hardcoded to
cam5_laundry and 1920x1088 - handoff step 3 says to adapt those before
applying it to another camera, so this takes them as arguments.

Checks a real fragmented MP4 (not just RTSP audio: an earlier iteration of the
pilot passed audio while the browser-format output contained only headers and
zero playable frames), then AAC and Opus pacing. Audio stays in memory; the
temporary MP4 is deleted. Proves signal and pacing, NOT audible quality,
latency, or browser playback.
"""
import array, json, math, subprocess, sys, tempfile, time, urllib.request

FFDIR = '/usr/lib/ffmpeg/7.0/bin'
stream = sys.argv[1] if len(sys.argv) > 1 else 'cam5_laundry'
width = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
height = int(sys.argv[3]) if len(sys.argv) > 3 else 1088
DURATION = 20
failed = False

url = (f'http://127.0.0.1:1984/api/stream.mp4?src={stream}'
       f'&video=h264&audio=aac&duration=12')
try:
    with urllib.request.urlopen(url, timeout=30) as r:
        data = r.read()
    with tempfile.NamedTemporaryFile(suffix='.mp4') as f:
        f.write(data); f.flush()
        p = subprocess.run(
            [f'{FFDIR}/ffprobe', '-v', 'error', '-count_frames', '-show_entries',
             'stream=codec_name,nb_read_frames,width,height,duration', '-of', 'json',
             f.name], capture_output=True, text=True, timeout=25)
        st = json.loads(p.stdout or '{}').get('streams', [])
        v = next((s for s in st if s.get('codec_name') == 'h264'), {})
        a = next((s for s in st if s.get('codec_name') == 'aac'), {})
        ok = (p.returncode == 0 and not p.stderr.strip()
              and v.get('width') == width and v.get('height') == height
              and int(v.get('nb_read_frames', 0)) > 0
              and int(a.get('nb_read_frames', 0)) > 0
              and float(v.get('duration', 0)) >= 5)
        print(json.dumps({'stream': stream, 'format': 'fragmented_mp4', 'ok': ok,
                          'bytes': len(data),
                          'video_frames': v.get('nb_read_frames'),
                          'aac_frames': a.get('nb_read_frames'),
                          'dims': f"{v.get('width')}x{v.get('height')}",
                          'tail': p.stderr[-300:]}), flush=True)
        failed |= not ok
except (OSError, ValueError, subprocess.TimeoutExpired) as e:
    print(json.dumps({'stream': stream, 'format': 'fragmented_mp4',
                      'ok': False, 'error': str(e)}), flush=True)
    failed = True

for codec in ('aac', 'opus'):
    cmd = [f'{FFDIR}/ffmpeg', '-hide_banner', '-loglevel', 'error',
           '-rtsp_transport', 'tcp', '-timeout', '10000000',
           '-analyzeduration', '1000000', '-probesize', '32768',
           '-i', f'rtsp://127.0.0.1:8554/{stream}?audio={codec}',
           '-t', str(DURATION), '-map', '0:a:0', '-vn',
           '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1']
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=DURATION + 25)
    except subprocess.TimeoutExpired:
        print(json.dumps({'stream': stream, 'codec': codec, 'ok': False,
                          'error': 'timeout'}), flush=True)
        failed = True; continue
    el = time.monotonic() - t0
    s = array.array('f', r.stdout)
    rms = math.sqrt(sum(x * x for x in s) / len(s)) if s else 0
    secs = len(s) / 16000
    err = r.stderr.decode(errors='replace').strip()
    ok = (r.returncode == 0 and not err and rms > 0
          and abs(secs - DURATION) < 0.5 and DURATION - 2 <= el <= DURATION + 10)
    print(json.dumps({'stream': stream, 'codec': codec, 'ok': ok,
                      'wall_seconds': round(el, 2),
                      'decoded_seconds': round(secs, 3),
                      'rms_dbfs': round(20 * math.log10(rms), 2) if rms else None,
                      'tail': err[-300:]}), flush=True)
    failed |= not ok

print(json.dumps({'stream': stream, 'RESULT': 'PASS' if not failed else 'FAIL'}))
raise SystemExit(int(failed))
