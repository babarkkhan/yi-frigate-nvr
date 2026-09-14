#!/usr/bin/env python3
"""Read-only relay/recording check, run on the VPS without invoking WSL.

This checks the private transport and Frigate authorization, not Google login,
public DNS/TLS, decodability, or notifications. Requires the private Caddy snippet.
"""
import argparse
import concurrent.futures
import json
from pathlib import Path
import shlex
import time
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--secret-file', default='/etc/caddy/cam-proxy-secret.caddy')
    parser.add_argument('--base-url', default='http://127.0.0.1:18971')
    parser.add_argument('--max-age', type=float, default=120)
    args = parser.parse_args()
    parts = shlex.split(Path(args.secret_file).read_text())
    if len(parts) != 3 or parts[:2] != ['header_up', 'X-Proxy-Secret']:
        raise ValueError('Expected a single X-Proxy-Secret header_up directive')
    secret = parts[2]
    headers = {'X-Proxy-Secret': secret, 'X-Forwarded-User': 'gateway-health',
               'X-Forwarded-Groups': 'viewer'}
    problems = []

    def get(path, request_headers=None):
        req = urllib.request.Request(args.base_url.rstrip('/') + path,
                                     headers=headers if request_headers is None else request_headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    for label, supplied in [('missing', {}), ('wrong', {'X-Proxy-Secret': 'invalid'})]:
        status, _ = get('/api/version', supplied)
        if status != 401:
            problems.append(f'{label} secret returned {status}, expected 401')
    status, body = get('/api/profile')
    profile = json.loads(body) if status == 200 else {}
    if profile.get('role') != 'viewer':
        problems.append('authenticated profile is not a viewer')
    status, _ = get('/api/users')
    if status != 403:
        problems.append(f'viewer user administration returned {status}, expected 403')
    status, body = get('/api/config')
    if status != 200 or secret.encode() in body:
        problems.append('config unavailable or contains unredacted proxy secret')
    config = json.loads(body) if status == 200 else {}
    expected = {name for name, camera in config.get('cameras', {}).items()
                if camera.get('enabled', True)}
    if not expected:
        problems.append('no enabled cameras in config')
    status, body = get('/api/stats')
    stats = json.loads(body) if status == 200 else {}
    now = time.time()

    def camera_check(camera):
        fps = stats.get('cameras', {}).get(camera, {}).get('camera_fps', 0)
        query = urllib.parse.urlencode({'after': now - 600, 'before': now})
        status, body = get('/api/' + urllib.parse.quote(camera, safe='') + '/recordings?' + query)
        recordings = json.loads(body) if status == 200 else []
        latest = max((r.get('end_time', 0) for r in recordings), default=0)
        age = round(time.time() - latest, 1) if latest else None
        return camera, {'fps': fps, 'recording_age_seconds': age,
                        # Segment end timestamps can lead wall time slightly.
                        'ok': fps > 0 and age is not None and -5 <= age <= args.max_age}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        cameras = dict(pool.map(camera_check, sorted(expected)))
    problems += [f'{camera}: capture or recording stale' for camera, state in cameras.items() if not state['ok']]
    print(json.dumps({'ok': not problems, 'problems': problems, 'cameras': cameras}, sort_keys=True))
    return 1 if problems else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Do not dump response bodies, credentials, or full configuration.
        print(json.dumps({'ok': False, 'error_type': type(error).__name__}))
        raise SystemExit(1)
