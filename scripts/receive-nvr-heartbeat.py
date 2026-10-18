#!/usr/bin/env python3
"""Forced SSH command: accept only a small health report, never commands/paths."""
import json
import os
from pathlib import Path
import signal
import sys
import time

signal.alarm(12)
raw = sys.stdin.buffer.read(8193)
if len(raw) > 8192:
    raise SystemExit(1)
data = json.loads(raw)
assert set(data) == {'ok', 'problems', 'at'} and isinstance(data['ok'], bool)
assert isinstance(data['problems'], list) and len(data['problems']) <= 20
assert all(isinstance(p, str) and len(p) <= 200 and '\n' not in p for p in data['problems'])
assert isinstance(data['at'], (int, float)) and abs(time.time()-data['at']) < 900
path = Path('/var/lib/nvr-home-heartbeat/latest.json')
tmp = path.with_suffix('.tmp')
with tmp.open('w') as f:
    json.dump({'received_at': time.time(), 'payload': data}, f)
    f.flush(); os.fsync(f.fileno())
os.chmod(tmp, 0o644)
os.replace(tmp, path)
print('accepted')
