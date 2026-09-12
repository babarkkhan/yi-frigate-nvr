#!/usr/bin/env python3
"""Bounded read-only sampling inside Frigate; opens NO camera RTSP sessions.

docker exec -i frigate python3 - --seconds 120 < scripts/observe-camera-disconnects.py
JSONL contains only selected operational fields, not full camera status/config.
Running this through WSL may wake WSL: this is not an availability monitor.
"""
import argparse
import concurrent.futures
import datetime
import json
from pathlib import Path
import socket
import sqlite3
import time
import urllib.request
from urllib.parse import urlsplit
import yaml


def get_json(url):
    with urllib.request.urlopen(url, timeout=4) as response:
        return json.load(response)


def camera_status(item):
    name, ip = item
    try:
        status = get_json(f'http://{ip}/cgi-bin/status.json')
        return name, {key: status.get(key) for key in
                      ('uptime', 'load_avg', 'free_memory', 'wlan_strength')}
    except Exception as error:
        return name, {'error': type(error).__name__}


def connections(ips):
    result = {name: {'established': 0, 'other': 0, 'rx_queue_bytes': 0}
              for name in ips}
    reverse = {ip: name for name, ip in ips.items()}
    for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
        fields = line.split()
        address, port = fields[2].split(':')
        ip = socket.inet_ntoa(bytes.fromhex(address)[::-1])
        if int(port, 16) != 554 or ip not in reverse:
            continue
        value = result[reverse[ip]]
        value['established' if fields[3] == '01' else 'other'] += 1
        value['rx_queue_bytes'] += int(fields[4].split(':')[1], 16)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 900:
        parser.error('--seconds must be 10..900')
    cfg = yaml.safe_load(Path('/config/config.yml').read_text())
    ips = {name: urlsplit(cam['ffmpeg']['inputs'][0]['path']).hostname
           for name, cam in cfg['cameras'].items() if cam.get('enabled', True)}
    if not ips:
        raise SystemExit('No expected cameras')
    deadline = time.monotonic() + args.seconds
    previous = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        while True:
            started = time.monotonic()
            row = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            statuses = dict(pool.map(camera_status, ips.items()))
            try:
                stats = get_json('http://127.0.0.1:5000/api/stats')['cameras']
                sockets = connections(ips)
                with sqlite3.connect('file:/config/frigate.db?mode=ro', uri=True,
                                     timeout=3) as db:
                    last = dict(db.execute('SELECT camera,MAX(end_time) FROM recordings GROUP BY camera'))
                for name, status in statuses.items():
                    status['capture_fps'] = stats.get(name, {}).get('camera_fps')
                    status['rtsp_tcp'] = sockets[name]
                    status['recording_age_s'] = round(time.time()-last[name], 1) if name in last else None
                    try:
                        uptime = float(status['uptime'])
                        status['uptime_decreased'] = name in previous and uptime < previous[name]
                        previous[name] = uptime
                    except (KeyError, TypeError, ValueError):
                        pass
                row['cameras'] = statuses
            except Exception as error:
                row.update(cameras=statuses, error=type(error).__name__)
            print(json.dumps(row), flush=True)
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(max(0, 10-(time.monotonic()-started)), remaining))


if __name__ == '__main__':
    main()
