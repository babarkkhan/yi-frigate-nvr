import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/nvr-monitor.py'
spec = importlib.util.spec_from_file_location('monitor', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def bad(fresh=False, api=True):
    return {'ok': False, 'api_ok': api, 'problems': ['cam1_mensroom: capture or recording stale'],
            'cameras': {'cam1_mensroom': {'ok': False, 'recording_ok': fresh}}}


class MonitorTests(unittest.TestCase):
    def test_three_failures_and_three_successes(self):
        state = {}
        for i in range(2):
            m.transition(state, bad(), 10000+i)
            self.assertNotIn('pending', state)
        m.transition(state, bad(), 10002)
        self.assertEqual(state['pending']['kind'], 'outage')
        state.pop('pending')
        m.transition(state, bad(), 10003)
        self.assertNotIn('pending', state)  # no repeat spam
        for i in range(2):
            m.transition(state, {'ok': True}, 10004+i)
            self.assertNotIn('pending', state)
        m.transition(state, {'ok': True}, 10006)
        self.assertEqual(state['pending']['kind'], 'recovered')

    def test_budget_and_cooldown_survive_restart(self):
        state = {'failures': 3, 'snapshot': bad(), 'attempts': [9900],
                 'last_attempt': 9900, 'incident_attempts': 1}
        cfg = {'mode': 'local', 'recovery_enabled': True}
        with tempfile.TemporaryDirectory() as t:
            path = Path(t)/'state.json'; m.atomic_json(path, state)
            state = m.json.loads(path.read_text())
        self.assertFalse(m.eligible(state, cfg, 10000))
        self.assertTrue(m.eligible(state, cfg, 10800))
        state['incident_attempts'] = 2
        self.assertFalse(m.eligible(state, cfg, 20000))

    def test_api_only_failure_does_not_interrupt_recording(self):
        state = {'failures': 10, 'snapshot': bad(fresh=True, api=False)}
        self.assertFalse(m.eligible(state, {'mode':'local','recovery_enabled':True}, 10000))

    def test_alert_only_for_unclassified_failure(self):
        state = {'failures': 10, 'snapshot': {'ok':False,'problems':['disk low']}}
        self.assertFalse(m.eligible(state, {'mode':'local','recovery_enabled':True},10000))

    def test_relay_never_runs_recovery(self):
        self.assertFalse(m.eligible({'failures':9,'snapshot':bad()},
                                   {'mode':'relay','recovery_enabled':True},10000))

    def test_failed_delivery_remains_pending(self):
        s={}
        for i in range(4):m.transition(s,bad(),10000+i)
        self.assertEqual(s['pending']['kind'],'outage')

    def test_native_probe_midnight_missing_and_zero_fps(self):
        now=m.dt.datetime(2026,10,18,0,0,20,tzinfo=m.dt.timezone.utc).timestamp()
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)/'2026-10-17/23/cam1_mensroom';folder.mkdir(parents=True)
            file=folder/'sample.mp4';file.write_bytes(b'test')
            m.os.utime(file,(now-40,now-40))
            cfg={'expected':['cam1_mensroom'],'recording_root':t,'disk_path':t,
                 'min_free_gib':0,'api_url':'http://localhost'}
            response=unittest.mock.MagicMock()
            response.__enter__.return_value.read.return_value=b'{"cameras":{"cam1_mensroom":{"camera_fps":5}}}'
            with patch.object(m.urllib.request,'urlopen',return_value=response):
                self.assertTrue(m.local_snapshot(cfg,now)['ok'])
                m.os.utime(file,(now-200,now-200))
                self.assertFalse(m.local_snapshot(cfg,now)['ok'])
                m.os.utime(file,(now-40,now-40))
                response.__enter__.return_value.read.return_value=b'{"cameras":{}}'
                self.assertFalse(m.local_snapshot(cfg,now)['ok'])
                response.__enter__.return_value.read.return_value=b'{"cameras":{"cam1_mensroom":{"camera_fps":0}}}'
                self.assertFalse(m.local_snapshot(cfg,now)['ok'])

    def test_native_probe_never_invokes_wsl(self):
        with tempfile.TemporaryDirectory() as t:
            cfg={'expected':['cam1_mensroom'],'recording_root':t,'disk_path':t,'min_free_gib':0,'api_url':'http://localhost'}
            with patch.object(m.urllib.request,'urlopen',side_effect=OSError), patch.object(m,'run') as run:
                self.assertFalse(m.local_snapshot(cfg,10000)['ok']);run.assert_not_called()

    def test_lock_excludes_second_process(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'test.lock'
            with m.Lock(path):
                code="import importlib.util; s=importlib.util.spec_from_file_location('m',"+repr(str(SCRIPT))+"); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.Lock("+repr(str(path))+").__enter__()"
                result=m.run([m.sys.executable,'-c',code],timeout=10)
                self.assertNotEqual(result.returncode,0)


if __name__ == '__main__':
    unittest.main()
