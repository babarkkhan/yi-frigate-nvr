#!/usr/bin/env python3
"""Measure a camera's RTSP audio track and its timestamp pacing.

  docker exec -i frigate python3 - <ip> <label> < scripts/probe-camera-audio.py

Handoff step 2 of docs/live-audio-pilot.md says not to assume cam5's
`asetpts` correction is needed elsewhere. This measures it.

HOW TO READ IT. The signal is decoded_seconds / requested_seconds, NOT
wall_seconds / decoded_seconds. `-t N` limits by the STREAM's timestamps, so
on a camera whose audio RTP clock advances at half real time, asking for N
seconds of stream time runs 2N real seconds and yields 2N seconds of real
samples. decoded/requested therefore lands at ~2.0 while wall/decoded looks
like a healthy ~1.0 and hides the fault entirely. An earlier version of this
script used wall/decoded and wrongly reported a clearly affected camera clean.
"""
import array, json, math, subprocess, sys, time

FF = '/usr/lib/ffmpeg/7.0/bin/ffmpeg'
FP = '/usr/lib/ffmpeg/7.0/bin/ffprobe'
ip = sys.argv[1] if len(sys.argv) > 1 else '192.168.3.22'
label = sys.argv[2] if len(sys.argv) > 2 else ip
DURATION = 10
url = f'rtsp://{ip}/ch0_0.h264'

def fail(reason):
    print(json.dumps({'camera': label, 'ok': False, 'error': reason,
                      'needs_asetpts': None, 'clock_runs_at': None}))
    raise SystemExit(1)


def run_checked(*args, **kwargs):
    try:
        result = subprocess.run(*args, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail(str(error))
    if result.returncode:
        tail = result.stderr if isinstance(result.stderr, str) else result.stderr.decode(errors='replace')
        fail(f'command exited {result.returncode}: {tail[-500:]}')
    return result


probe = run_checked(
    [FP, '-v', 'error', '-rtsp_transport', 'tcp', '-timeout', '12000000',
     '-show_entries', 'stream=codec_name,codec_type,sample_rate,channels,width,height',
     '-of', 'json', url], capture_output=True, text=True, timeout=45)
try:
    streams = json.loads(probe.stdout or '{}').get('streams', [])
except (ValueError, AttributeError):
    fail('invalid ffprobe response')
audio = next((s for s in streams if s.get('codec_type') == 'audio'), {})
if not audio:
    fail('source has no audio track')

start = time.monotonic()
pull = run_checked(
    [FF, '-hide_banner', '-loglevel', 'error', '-rtsp_transport', 'tcp',
     '-timeout', '12000000', '-allowed_media_types', 'audio', '-i', url, '-t', str(DURATION),
     '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'],
    capture_output=True, timeout=DURATION + 40)
elapsed = time.monotonic() - start

if pull.stderr.strip():
    fail(pull.stderr.decode(errors='replace').strip()[-500:])
try:
    samples = array.array('f', pull.stdout)
except ValueError:
    fail('partial audio sample in output')
secs = len(samples) / 16000
if secs < DURATION * 0.9 or any(not math.isfinite(s) for s in samples):
    fail('insufficient or invalid audio samples; clock measurement unavailable')
rms = math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0

# decoded / requested is the discriminating ratio - see the docstring.
overrun = (secs / DURATION) if DURATION else None

print(json.dumps({
    'camera': label, 'ip': ip,
    'ok': True,
    'audio_codec': audio.get('codec_name'),
    'sample_rate': audio.get('sample_rate'),
    'channels': audio.get('channels'),
    'video': next((f"{s.get('width')}x{s.get('height')}" for s in streams
                   if s.get('codec_type') == 'video'), None),
    'requested_seconds': DURATION,
    'decoded_seconds': round(secs, 3),
    'wall_seconds': round(elapsed, 2),
    'decoded_per_requested': round(overrun, 2) if overrun else None,
    'clock_runs_at': (f"{round(1/overrun, 2)}x real time" if overrun else None),
    'needs_asetpts': (overrun is not None and overrun > 1.5),
    'rms_dbfs': round(20 * math.log10(rms), 2) if rms else None,
    'stderr_tail': pull.stderr.decode(errors='replace').strip()[-200:],
}, indent=2))
