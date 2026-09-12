"""Regression tests: a failed measurement must never become a clean clock verdict."""
import array
import contextlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/probe-camera-audio.py'


class AudioProbeTests(unittest.TestCase):
    def probe(self, results):
        output = io.StringIO()
        with patch('subprocess.run', side_effect=results), \
             patch('sys.argv', [str(SCRIPT), '192.0.2.1', 'test']), \
             contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(SCRIPT), run_name='__main__')
                code = 0
            except SystemExit as e:
                code = e.code
        return code, json.loads(output.getvalue())

    def metadata(self, audio=True):
        tracks = [{'codec_type': 'audio', 'codec_name': 'pcm_s16be',
                   'sample_rate': '8000', 'channels': 1}] if audio else []
        return subprocess.CompletedProcess([], 0, json.dumps({'streams': tracks}), '')

    def pcm(self, seconds):
        return subprocess.CompletedProcess([], 0, array.array('f', [0.01] * int(16000 * seconds)).tobytes(), b'')

    def assert_invalid(self, results):
        code, result = self.probe(results)
        self.assertNotEqual(code, 0)
        self.assertFalse(result['ok'])
        self.assertIsNone(result['needs_asetpts'])
        self.assertIsNone(result['clock_runs_at'])

    def test_missing_track_is_invalid(self):
        self.assert_invalid([self.metadata(False)])

    def test_failed_decode_is_invalid(self):
        self.assert_invalid([self.metadata(), subprocess.CompletedProcess([], 1, b'', b'connection failed')])

    def test_timeout_is_invalid(self):
        self.assert_invalid([subprocess.TimeoutExpired('ffprobe', 45)])

    def test_partial_capture_is_invalid(self):
        self.assert_invalid([self.metadata(), self.pcm(2)])

    def test_valid_normal_clock(self):
        code, result = self.probe([self.metadata(), self.pcm(10)])
        self.assertEqual(code, 0)
        self.assertTrue(result['ok'])
        self.assertFalse(result['needs_asetpts'])

    def test_valid_half_speed_clock(self):
        code, result = self.probe([self.metadata(), self.pcm(20)])
        self.assertEqual(code, 0)
        self.assertTrue(result['needs_asetpts'])


if __name__ == '__main__':
    unittest.main()
