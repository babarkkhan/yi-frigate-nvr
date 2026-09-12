#!/usr/bin/env python3
"""Decode the cam5 live-audio pilot without retaining microphone audio.

Run inside the Frigate container:
  docker exec -i frigate python3 < scripts/verify-live-audio.py
This verifies codecs, signal, and media pacing, not audible quality or latency.
The temporary 12-second MP4 sample is deleted when its check finishes.
Running it through WSL starts that distro; it is not an availability probe.
"""
import array
import json
import math
import subprocess
import tempfile
import time
import urllib.request

FFMPEG = '/usr/lib/ffmpeg/7.0/bin/ffmpeg'
DURATION = 20


def main():
    failed = False
    # Test actual fragmented MP4 too: RTSP audio alone previously passed while
    # browser-format output contained only headers and zero playable frames.
    mp4_url = ('http://127.0.0.1:1984/api/stream.mp4?src=cam5_laundry'
               '&video=h264&audio=aac&duration=12')
    try:
        with urllib.request.urlopen(mp4_url, timeout=25) as response:
            data = response.read()
        with tempfile.NamedTemporaryFile(suffix='.mp4') as sample:
            sample.write(data)
            sample.flush()
            result = subprocess.run(
                [FFMPEG.rsplit('/', 1)[0] + '/ffprobe', '-v', 'error', '-count_frames',
                 '-show_entries', 'stream=codec_name,nb_read_frames,width,height,duration',
                 '-of', 'json', sample.name], capture_output=True, text=True, timeout=20)
            streams = json.loads(result.stdout).get('streams', [])
            video = next((s for s in streams if s.get('codec_name') == 'h264'), {})
            audio = next((s for s in streams if s.get('codec_name') == 'aac'), {})
            ok = (result.returncode == 0 and not result.stderr.strip()
                  and video.get('width') == 1920 and video.get('height') == 1088
                  and int(video.get('nb_read_frames', 0)) > 0
                  and int(audio.get('nb_read_frames', 0)) > 0
                  and float(video.get('duration', 0)) >= 5)
            print(json.dumps({'format': 'fragmented_mp4', 'ok': ok, 'bytes': len(data),
                              'streams': streams, 'diagnostic_tail': result.stderr[-500:]}), flush=True)
            failed |= not ok
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'format': 'fragmented_mp4', 'ok': False,
                          'error': str(error)}), flush=True)
        failed = True
    for codec in ('aac', 'opus'):
        url = f'rtsp://127.0.0.1:8554/cam5_laundry?audio={codec}'
        command = [FFMPEG, '-hide_banner', '-loglevel', 'error',
                   '-rtsp_transport', 'tcp', '-timeout', '10000000',
                   '-analyzeduration', '1000000', '-probesize', '32768',
                   '-i', url, '-t', str(DURATION), '-map', '0:a:0', '-vn',
                   '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1']
        start = time.monotonic()
        try:
            result = subprocess.run(command, capture_output=True, timeout=DURATION + 20)
        except subprocess.TimeoutExpired:
            print(json.dumps({'codec': codec, 'ok': False, 'error': 'timeout'}), flush=True)
            failed = True
            continue
        elapsed = time.monotonic() - start
        samples = array.array('f', result.stdout)
        rms = math.sqrt(sum(s*s for s in samples)/len(samples)) if samples else 0
        seconds = len(samples)/16000
        errors = result.stderr.decode(errors='replace').strip()
        ok = (result.returncode == 0 and not errors and rms > 0
              and abs(seconds - DURATION) < 0.5
              and DURATION - 2 <= elapsed <= DURATION + 10)
        print(json.dumps({'codec': codec, 'ok': ok, 'exit': result.returncode,
                          'wall_seconds': round(elapsed, 2),
                          'decoded_seconds': round(seconds, 3),
                          'rms_dbfs': round(20*math.log10(rms), 2) if rms else None,
                          'diagnostic_tail': errors[-500:]}), flush=True)
        failed |= not ok
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
