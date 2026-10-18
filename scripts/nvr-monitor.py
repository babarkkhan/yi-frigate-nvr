#!/usr/bin/env python3
"""Native Windows observer/recovery controller or independent VPS alert monitor.

No WSL invocation until persisted, repeated local capture/recording failure.
Configuration, state and notification credentials stay outside the public tree.
"""
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from email.message import EmailMessage


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Lock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
    def __enter__(self):
        self.file.seek(0)
        if os.name == 'nt':
            import msvcrt
            if self.file.read(1) == b'':
                self.file.write(b'0'); self.file.flush()
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return self
    def __exit__(self, *args):
        self.file.close()


def run(args, timeout=30, input=None):
    # Child process output is not logged: it may contain private configuration.
    return subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout)


def local_snapshot(cfg, now):
    cameras, problems = {}, []
    root = Path(cfg['recording_root'])
    for name in cfg['expected']:
        latest = None
        for age in (0, 3600):
            stamp = dt.datetime.fromtimestamp(now-age, dt.timezone.utc)
            folder = root / stamp.strftime('%Y-%m-%d') / stamp.strftime('%H') / name
            for path in folder.glob('*.mp4'):
                try:
                    stat = path.stat()
                    if stat.st_size > 0 and (latest is None or stat.st_mtime > latest):
                        latest = stat.st_mtime
                except FileNotFoundError:
                    pass
        cameras[name] = {'recording_age_seconds': None if latest is None else round(now-latest, 1)}
    try:
        with urllib.request.urlopen(cfg['api_url'].rstrip('/')+'/api/stats', timeout=8) as r:
            stats = json.load(r)
        api_ok = True
    except (OSError, ValueError):
        api_ok = False
        stats = {}
        problems.append('Frigate API unavailable')
    for name, value in cameras.items():
        fps = stats.get('cameras', {}).get(name, {}).get('camera_fps')
        value['fps'] = fps
        age = value['recording_age_seconds']
        value['recording_ok'] = age is not None and -30 <= age <= 120
        value['ok'] = (isinstance(fps, (float, int)) and not isinstance(fps, bool)
                       and math.isfinite(fps) and 1 <= fps < 1000 and value['recording_ok'])
        if not value['ok']:
            problems.append(name + ': capture or recording stale')
    free = shutil.disk_usage(cfg['disk_path']).free / (1024**3)
    if free < cfg.get('min_free_gib', 30):
        problems.append('Recording disk space low')
    if cfg.get('lan_gateway'):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((cfg['lan_gateway'], 9))
            source = s.getsockname()[0]
        if source != cfg['expected_lan_ip']:
            problems.append('NVR LAN address changed; speaker access may fail')
    return {'ok': not problems, 'api_ok': api_ok, 'cameras': cameras,
            'free_gib': round(free, 1), 'problems': problems, 'at': now}


def relay_snapshot(cfg, now):
    result = run([sys.executable, cfg['checker'], '--expected', *cfg['expected']], timeout=100)
    data = json.loads(result.stdout)
    if not isinstance(data.get('ok'), bool):
        raise ValueError('Invalid gateway check')
    data['at'] = now
    # Public HTTPS must redirect anonymous callers into OAuth, never expose media.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None
    try:
        urllib.request.build_opener(NoRedirect).open(cfg['public_url'], timeout=10)
        code = 200
    except urllib.error.HTTPError as e:
        code = e.code
    if code not in (302, 303, 307, 308):
        data.setdefault('problems', []).append('Public HTTPS authentication redirect failed')
        data['ok'] = False
    if cfg.get('heartbeat_file'):
        try:
            heartbeat = json.loads(Path(cfg['heartbeat_file']).read_text())
            if not -30 <= now-heartbeat['received_at'] <= 240:
                raise ValueError('Stale heartbeat')
            if not heartbeat['payload']['ok']:
                data.setdefault('problems', []).extend(heartbeat['payload']['problems'])
                data['ok'] = False
        except (OSError, ValueError, KeyError, TypeError):
            data.setdefault('problems', []).append('Windows watchdog heartbeat missing or stale')
            data['ok'] = False
    return data


def transition(state, snapshot, now):
    """Debounce both edges; retain notification retries and recovery budgets."""
    state['failures'] = 0 if snapshot['ok'] else state.get('failures', 0)+1
    state['successes'] = state.get('successes', 0)+1 if snapshot['ok'] else 0
    state['attempts'] = [x for x in state.get('attempts', []) if now-x < 3600]
    if state['failures'] >= 3 and state.get('status') != 'down':
        state['status'] = 'down'
        state['down_since'] = now
        state['pending'] = {'kind': 'outage', 'at': now, 'problems': snapshot.get('problems', ['Health check failed'])}
    elif state['successes'] >= 3:
        if state.get('status') == 'down':
            state['pending'] = {'kind': 'recovered', 'at': now, 'down_since': state.get('down_since')}
        state['status'] = 'up'
        state['incident_attempts'] = 0
    state['snapshot'] = snapshot
    return state


def eligible(state, cfg, now):
    snap = state['snapshot']
    # An unavailable API with advancing files must not sacrifice recordings.
    any_fresh = any(x.get('recording_ok') for x in snap.get('cameras', {}).values())
    bad = [name for name, x in snap.get('cameras', {}).items() if not x['ok']]
    return (cfg.get('recovery_enabled', False) and cfg['mode'] == 'local'
            and state.get('failures', 0) >= 3 and bool(bad)
            and (snap.get('api_ok') or not any_fresh)
            and now-state.get('last_attempt', 0) >= 900
            and len(state.get('attempts', [])) < 2
            and state.get('incident_attempts', 0) < 2)


def notify(cfg, event):
    n = cfg.get('notify', {})
    if not n:
        return False
    text = 'Home cameras: ' + event['kind'].upper()
    if event.get('problems'):
        text += '\n' + '\n'.join(event['problems'])
    text += '\n' + cfg['public_url']
    if n['type'] == 'telegram':
        payload = json.dumps({'chat_id': n['chat_id'], 'text': text, 'disable_web_page_preview': True}).encode()
        req = urllib.request.Request('https://api.telegram.org/bot'+n['token']+'/sendMessage',
                                     data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as r:
            if not json.load(r).get('ok'):
                raise RuntimeError('Notification rejected')
    elif n['type'] == 'smtp':
        msg = EmailMessage()
        msg['From'], msg['To'], msg['Subject'] = n['from'], n['to'], text.splitlines()[0]
        msg.set_content(text)
        with smtplib.SMTP(n['host'], n.get('port', 587), timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(n['username'], n['password'])
            smtp.send_message(msg)
    else:
        raise ValueError('Unknown notification delivery type')
    return True


def recover(cfg, snapshot):
    prefix = ['wsl.exe', '-d', cfg['distro'], '-u', 'root', '--']
    worker = cfg['wsl_repo']+'/scripts/nvr-recover.py'
    request = json.dumps({'expected': cfg['expected'], 'snapshot': snapshot, 'repo': cfg['wsl_repo']})
    r = run(prefix+['python3', worker, 'diagnose'], timeout=40, input=request)
    if r.returncode:
        return {'action': 'none', 'error': 'Recovery diagnosis failed'}
    diagnosis = json.loads(r.stdout)
    action = diagnosis['action']
    if action == 'gpu-reset':
        if not cfg.get('allow_wsl_reset', False):
            return {'action': 'none', 'error': 'GPU reset requires enablement'}
        # Preserve all other distros. Budget is saved on Windows before this.
        run(prefix+['docker', 'stop', '-t', '20', 'tailscale', 'frigate'], timeout=65)
        run(['wsl.exe', '--terminate', cfg['distro']], timeout=35)
        # WSL may share its VM with other distros. Never escalate to global shutdown.
        gpu = run(prefix+['timeout', '15', '/usr/lib/wsl/lib/nvidia-smi', '-L'], timeout=50)
        if gpu.returncode:
            return {'action': action, 'error': 'GPU still unavailable; no broader restart attempted'}
        run(prefix+['systemctl', 'start', 'docker', 'home-nvr-tunnel'], timeout=30)
        result = run(prefix+['bash', cfg['wsl_repo']+'/scripts/restart-nvr.sh', '--apply'], timeout=330)
        return {'action': action, 'exit_code': result.returncode}
    if action == 'none':
        return diagnosis
    request = json.dumps({'expected': cfg['expected'], 'snapshot': snapshot, 'repo': cfg['wsl_repo'], 'diagnosis': diagnosis})
    r = run(prefix+['python3', worker, 'apply'], timeout=330, input=request)
    return json.loads(r.stdout) if r.returncode == 0 else {'action': action, 'error': 'Recovery worker failed'}


def publish(cfg, snapshot):
    target = cfg.get('heartbeat_ssh')
    if not target:
        return
    # The dedicated server key can only submit this bounded health object.
    args = ['ssh.exe', '-T', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
            '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile='+target['known_hosts'], '-i', target['key'], target['destination']]
    payload = {'ok': snapshot['ok'], 'problems': snapshot.get('problems', []), 'at': snapshot['at']}
    r = run(args, timeout=35, input=json.dumps(payload))
    if r.returncode:
        raise RuntimeError('Heartbeat delivery failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--test-notification', action='store_true')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    import re
    if not cfg.get('expected') or any(not re.fullmatch(r'cam[1-6]_[a-z]+', c) for c in cfg['expected']):
        raise ValueError('Expected a nonempty explicit camera list')
    folder = Path(cfg['state_dir']); folder.mkdir(parents=True, exist_ok=True)
    with Lock(folder/'monitor.lock'):
        now = time.time()
        if args.test_notification:
            if not notify(cfg, {'kind': 'test', 'at': now}):
                raise RuntimeError('No notification destination configured')
            print('Test notification accepted by delivery service')
            return
        path = folder/'state.json'
        state = json.loads(path.read_text()) if path.exists() else {}
        maintenance = folder/'maintenance.json'
        if maintenance.exists() and json.loads(maintenance.read_text()).get('until', 0) > now:
            atomic_json(folder/'last-run.json', {'at': now, 'maintenance': True})
            return
        try:
            snapshot = local_snapshot(cfg, now) if cfg['mode'] == 'local' else relay_snapshot(cfg, now)
        except Exception as e:
            snapshot = {'ok': False, 'problems': ['Monitor check failed: '+type(e).__name__], 'at': now}
        if args.dry_run:
            print(json.dumps(snapshot)); return
        # Preserve evidence before any action that can wake or repair WSL.
        state = transition(state, snapshot, now)
        atomic_json(path, state)
        atomic_json(folder/'last-run.json', {'at': now, 'ok': snapshot['ok']})
        try:
            publish(cfg, snapshot)
            state.pop('heartbeat_error', None)
        except Exception as e:
            state['heartbeat_error'] = type(e).__name__
        atomic_json(path, state)
        if cfg.get('commission_on_success') and snapshot['ok'] and not state.get('heartbeat_error'):
            # Runs under the real scheduled-task account. Diagnosis is read-only.
            request = json.dumps({'expected': cfg['expected'], 'snapshot': snapshot, 'repo': cfg['wsl_repo']})
            try:
                check = run(['wsl.exe', '-d', cfg['distro'], '-u', 'root', '--', 'python3',
                             cfg['wsl_repo']+'/scripts/nvr-recover.py', 'diagnose'], timeout=40, input=request)
                if check.returncode == 0 and json.loads(check.stdout).get('action') == 'none':
                    cfg['recovery_enabled'] = True
                    cfg['commission_on_success'] = False
                    atomic_json(args.config, cfg)
                    state['commissioned_at'] = time.time()
                    state.pop('commission_error', None)
                else:
                    state['commission_error'] = 'Read-only WSL diagnosis did not pass'
            except Exception as e:
                state['commission_error'] = type(e).__name__
            atomic_json(path, state)
        if state.get('pending') and now-state.get('notify_attempt', 0) >= 300:
            state['notify_attempt'] = now
            try:
                if notify(cfg, state['pending']):
                    state['last_notification'] = state.pop('pending')
                    state.pop('notify_error', None)
            except Exception as e:
                state['notify_error'] = type(e).__name__
            atomic_json(path, state)
        if eligible(state, cfg, now):
            # A second fresh observation protects against stale repair decisions.
            fresh = local_snapshot(cfg, time.time())
            check = dict(state, snapshot=fresh)
            if not fresh['ok'] and eligible(check, cfg, time.time()):
                state['last_attempt'] = now
                state['attempts'].append(now)
                state['incident_attempts'] = state.get('incident_attempts', 0)+1
                atomic_json(path, state)
                evidence = folder / ('recovery-'+str(int(now))+'.json')
                atomic_json(evidence, {'before': fresh, 'at': now})
                try:
                    result = recover(cfg, fresh)
                except Exception as e:
                    result = {'error': type(e).__name__}
                state['last_recovery'] = {'at': now, **result}
                atomic_json(path, state)
                atomic_json(evidence, {'before': fresh, 'at': now, 'result': result})
                # Keep only this monitor's latest 30 bounded diagnostic records.
                for old in sorted(folder.glob('recovery-*.json'))[:-30]:
                    old.unlink()
        print(json.dumps({'ok': snapshot['ok'], 'status': state.get('status', 'checking'),
                          'recovery': state.get('last_recovery'), 'notification_pending': bool(state.get('pending'))}))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({'ok': False, 'error_type': type(e).__name__}))
        raise SystemExit(1)
