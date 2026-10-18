#!/usr/bin/env python3
"""Bounded WSL recovery worker; called only after the Windows observation phase."""
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import urllib.request


def run(args, timeout=20, input=None):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=input)


def rtsp_responds(host):
    try:
        with socket.create_connection((host, 554), 2) as s:
            s.settimeout(2)
            s.sendall(f'OPTIONS rtsp://{host}/ch0_0.h264 RTSP/1.0\r\nCSeq: 1\r\n\r\n'.encode())
            return s.recv(256).startswith(b'RTSP/1.0 200')
    except OSError:
        return False


def fresh_state(expected):
    code = '''import json,sqlite3,time,urllib.request
s=json.load(urllib.request.urlopen('http://127.0.0.1:5000/api/stats',timeout=5))
with sqlite3.connect('file:/config/frigate.db?mode=ro',uri=True,timeout=3) as db:
 ends=dict(db.execute('select camera,max(end_time) from recordings group by camera'))
print(json.dumps({c:{'fps':v.get('camera_fps',0),'age':time.time()-ends.get(c,0)} for c,v in s.get('cameras',{}).items()}))
'''
    try:
        r = run(['docker', 'exec', 'frigate', 'python3', '-c', code], timeout=12)
        data = json.loads(r.stdout)
        return [c for c in expected if not (data.get(c, {}).get('fps', 0) >= 1
                and -30 <= data.get(c, {}).get('age', 1e10) <= 120)]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return list(expected)


def diagnose(request):
    expected = request['expected']
    failed = fresh_state(expected)
    if not failed:
        return {'action': 'none', 'reason': 'Capture and recording recovered before repair'}
    gpu = run(['timeout', '12', '/usr/lib/wsl/lib/nvidia-smi', '-L'], timeout=15)
    if len(failed) == len(expected) and gpu.returncode:
        return {'action': 'gpu-reset', 'reason': 'All capture failed and WSL GPU probe failed'}
    running = run(['docker', 'inspect', '-f', '{{.State.Running}}', 'frigate'], timeout=8)
    if running.returncode or running.stdout.strip() != 'true':
        return {'action': 'stack', 'reason': 'NVR container unavailable'}
    hosts = {}
    for name in failed:
        private = Path(request['repo'])/'secrets'/(name.split('_')[0]+'-live-admin.json')
        if private.exists():
            hosts[name] = json.loads(private.read_text())['host']
    stalled, reachable = [], []
    for name, host in hosts.items():
        try:
            with socket.create_connection((host, 22), 2):
                reachable.append(name)
        except OSError:
            continue
        if not rtsp_responds(host):
            stalled.append(name)
    if stalled:
        return {'action': 'cameras', 'cameras': stalled, 'reason': 'SSH reachable but RTSP protocol failed'}
    if len(failed) == len(expected) and len(reachable) == len(expected) and not gpu.returncode:
        return {'action': 'stack', 'reason': 'All recording stale; GPU and camera RTSP respond'}
    return {'action': 'none', 'reason': 'No safe classified repair; offline or ambiguous camera failure'}


# Keys arrive through stdin and remain in container process memory only.
CAMERA_WORKER = r'''
import io,json,sys,time
sys.path.insert(0,'/config/.live-talk/vendor')
import paramiko
d=json.load(sys.stdin)
c=paramiko.SSHClient()
for line in d['known_hosts'].splitlines():
 e=paramiko.hostkeys.HostKeyEntry.from_line(line)
 if e:
  for h in e.hostnames:c.get_host_keys().add(h,e.key.get_name(),e.key)
c.connect(d['host'],username='root',pkey=paramiko.RSAKey.from_private_key(io.StringIO(d['private_key'])),look_for_keys=False,allow_agent=False,timeout=5,auth_timeout=5,banner_timeout=5)
try:
 cmd='export PATH=/home/yi-hack/bin:/home/yi-hack/sbin:$PATH; export LD_LIBRARY_PATH=/home/yi-hack/lib:/home/lib; /home/yi-hack/script/service.sh rtsp stop >/tmp/nvr-auto-recovery.log 2>&1; killall h264grabber_h h264grabber_l h264grabber >>/tmp/nvr-auto-recovery.log 2>&1; sleep 2; /home/yi-hack/script/service.sh rtsp start >>/tmp/nvr-auto-recovery.log 2>&1 </dev/null; echo service-start-requested'
 _,o,e=c.exec_command(cmd,timeout=12)
 data=o.read();e.read()
 if o.channel.recv_exit_status()!=0 or b'service-start-requested' not in data:raise RuntimeError('Service restart failed')
 print(json.dumps({'requested':True}))
finally:c.close()
'''


def apply(request):
    import fcntl
    # Same lock used by the coordinated manual NVR restart helper.
    with open('/tmp/home-nvr-restart.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Re-diagnose immediately; never execute a stale proposed repair.
        d = diagnose(request)
        if d['action'] != request['diagnosis']['action']:
            return {'action': 'none', 'reason': 'Diagnosis changed before apply'}
        if d['action'] == 'cameras':
            result = {}
            for name in d['cameras']:
                keypath = Path(request['repo'])/'secrets'/(name.split('_')[0]+'-live-admin.json')
                try:
                    r = run(['docker', 'exec', '-i', 'frigate', 'python3', '-c', CAMERA_WORKER],
                            timeout=25, input=keypath.read_text())
                    result[name] = 'restart-requested' if r.returncode == 0 else 'restart-failed'
                except Exception as e:
                    result[name] = type(e).__name__
            return {'action': 'cameras', 'results': result}
        if d['action'] != 'stack':
            return d
    # The helper acquires its own same lock; Windows holds the outer controller lock.
    run(['systemctl', 'start', 'docker'], timeout=25)
    r = run(['bash', request['repo']+'/scripts/restart-nvr.sh', '--apply'], timeout=300)
    return {'action': 'stack', 'exit_code': r.returncode}


if __name__ == '__main__':
    try:
        request = json.load(sys.stdin)
        assert request['expected'] and all(re.fullmatch(r'cam[1-6]_[a-z]+', c) for c in request['expected'])
        assert Path(request['repo']).is_absolute()
        if sys.argv[1] == 'diagnose':
            print(json.dumps(diagnose(request)))
        elif sys.argv[1] == 'apply':
            print(json.dumps(apply(request)))
        else:
            raise ValueError('Unknown action')
    except Exception as e:
        print(json.dumps({'action': 'none', 'error_type': type(e).__name__}))
        raise SystemExit(1)
