#!/usr/bin/env python3
"""Fail-closed local NVR check. Run inside Frigate; does not prove remote access."""
import json
from pathlib import Path
import sqlite3
import time
import urllib.request


def assess(stats, cameras, recording_ends, now):
    expected = [name for name, value in cameras.items() if value.get('enabled', True)]
    if not expected:
        return ['No enabled cameras configured']
    problems = []
    actual = stats.get('cameras', {})
    for name in expected:
        data = actual.get(name)
        if data is None:
            problems.append(f'{name}: missing from stats')
        else:
            fps = data.get('camera_fps')
            if not isinstance(fps, (int, float)) or not 1 <= fps < 1000:
                problems.append(f'{name}: invalid/no capture FPS ({fps})')
        if cameras[name].get('record', {}).get('enabled', True):
            end = recording_ends.get(name)
            if not isinstance(end, (int, float)) or not -30 <= now-end <= 120:
                problems.append(f'{name}: missing/stale/invalid recording timestamp')
    return problems


def main():
    import yaml
    try:
        cfg = yaml.safe_load(Path('/config/config.yml').read_text())
        with urllib.request.urlopen('http://127.0.0.1:5000/api/stats', timeout=10) as r:
            stats = json.load(r)
        with sqlite3.connect('file:/config/frigate.db?mode=ro', uri=True, timeout=5) as db:
            ends = dict(db.execute('SELECT camera,MAX(end_time) FROM recordings GROUP BY camera'))
        cameras = {name: dict(cam, record=dict(cfg.get('record', {}), **cam.get('record', {})))
                   for name, cam in cfg['cameras'].items()}
        problems = assess(stats, cameras, ends, time.time())
        print(json.dumps({'ok': not problems, 'problems': problems,
                          'capture_fps': {k: v.get('camera_fps') for k, v in stats.get('cameras', {}).items()}}))
        return int(bool(problems))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': type(error).__name__, 'detail': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
