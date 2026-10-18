import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('recover',Path(__file__).resolve().parents[1]/'scripts/nvr-recover.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def result(code=0,text='true'):
    return SimpleNamespace(returncode=code,stdout=text,stderr='')

class RecoveryTests(unittest.TestCase):
    def test_recovered_does_not_touch_gpu_or_services(self):
        with patch.object(r,'fresh_state',return_value=[]),patch.object(r,'run') as run:
            self.assertEqual(r.diagnose({'expected':['cam1_mensroom']})['action'],'none')
            run.assert_not_called()

    def test_gpu_reset_requires_all_cameras_failed(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'fresh_state',return_value=['cam1_mensroom']),patch.object(r,'run',side_effect=[result(1),result()]):
            d=r.diagnose({'expected':['cam1_mensroom','cam2_living'],'repo':t})
            self.assertEqual(d['action'],'none')
        with patch.object(r,'fresh_state',return_value=['cam1_mensroom']),patch.object(r,'run',return_value=result(1)):
            self.assertEqual(r.diagnose({'expected':['cam1_mensroom']})['action'],'gpu-reset')

    def test_offline_camera_never_triggers_stack_restart(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'secrets').mkdir()
            (Path(t)/'secrets/cam1-live-admin.json').write_text('{"host":"192.0.2.1"}')
            with patch.object(r,'fresh_state',return_value=['cam1_mensroom']),patch.object(r,'run',return_value=result()),patch.object(r.socket,'create_connection',side_effect=OSError):
                self.assertEqual(r.diagnose({'expected':['cam1_mensroom'],'repo':t})['action'],'none')

    def test_only_reachable_failed_rtsp_is_targeted(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'secrets').mkdir()
            (Path(t)/'secrets/cam1-live-admin.json').write_text('{"host":"192.0.2.1"}')
            with patch.object(r,'fresh_state',return_value=['cam1_mensroom']),patch.object(r,'run',return_value=result()),patch.object(r.socket,'create_connection') as connect,patch.object(r,'rtsp_responds',return_value=False):
                connect.return_value.__enter__.return_value=None
                d=r.diagnose({'expected':['cam1_mensroom','cam2_living'],'repo':t})
                self.assertEqual(d['action'],'cameras');self.assertEqual(d['cameras'],['cam1_mensroom'])

if __name__=='__main__':unittest.main()
