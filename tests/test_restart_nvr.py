"""Exercise recovery sequencing without touching Docker or the live system."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
MOCK_DOCKER = '''#!/usr/bin/env python3
import json,os,sys
a=sys.argv[1:]
with open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps(a)+'\\n')
if 'config' in a and '--images' in a:
    print('example/image@sha256:'+'a'*64 if not os.getenv('UNPINNED') else 'example/image:stable')
if 'up' in a and a[-1]=='frigate' and os.getenv('FAIL_FRIGATE'): sys.exit(1)
'''


@unittest.skipUnless(shutil.which('bash') and os.name == 'posix', 'Linux/WSL shell checks')
class RestartTests(unittest.TestCase):
    def run_case(self, mode, **variables):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'scripts').mkdir()
            (root/'bin').mkdir()
            for name in ('restart-nvr.sh', 'nvr-status.sh', 'check-nvr.py'):
                (root/'scripts'/name).write_text((ROOT/'scripts'/name).read_text())
            for name, body in {'docker': MOCK_DOCKER, 'sleep': '#!/bin/sh\nexit 0\n'}.items():
                target = root/'bin'/name
                target.write_text(body)
                target.chmod(0o755)
            log = root/'calls'
            env = dict(os.environ, PATH=str(root/'bin')+os.pathsep+os.environ['PATH'], CALL_LOG=str(log), **variables)
            result = subprocess.run(['bash', str(root/'scripts/restart-nvr.sh'), mode],
                                    env=env, text=True, capture_output=True, timeout=10)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            return result, calls

    def test_check_never_mutates(self):
        result, calls = self.run_case('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any('up' in call or 'stop' in call for call in calls))

    def test_missing_pin_prevents_mutation(self):
        result, calls = self.run_case('--apply', UNPINNED='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('up' in call or 'stop' in call for call in calls))

    def test_failed_frigate_does_not_start_sidecar(self):
        result, calls = self.run_case('--apply', FAIL_FRIGATE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any('up' in call and call[-1]=='tailscale' for call in calls))

    def test_healthy_sequence_waits_and_never_pulls(self):
        result, calls = self.run_case('--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        operations = [call for call in calls if 'up' in call or 'stop' in call]
        self.assertEqual([call[-1] for call in operations], ['tailscale', 'frigate', 'tailscale'])
        for call in operations[1:]:
            self.assertIn('--wait', call)
            self.assertEqual(call[call.index('--pull')+1], 'never')
