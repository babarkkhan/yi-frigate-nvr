import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('check_nvr', Path(__file__).parents[1]/'scripts/check-nvr.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class NvrCheckTests(unittest.TestCase):
    def test_empty_config_fails(self):
        self.assertTrue(check.assess({}, {}, {}, 1000))

    def test_missing_camera_fails(self):
        self.assertTrue(check.assess({'cameras': {}}, {'cam': {}}, {'cam': 999}, 1000))

    def test_missing_stale_future_recordings_fail(self):
        for ends in ({}, {'cam': 800}, {'cam': 1100}):
            with self.subTest(ends=ends):
                self.assertTrue(check.assess({'cameras': {'cam': {'camera_fps': 5}}}, {'cam': {}}, ends, 1000))

    def test_zero_and_nonfinite_fps_fail(self):
        for fps in (0, None, float('nan'), float('inf')):
            with self.subTest(fps=fps):
                self.assertTrue(check.assess({'cameras': {'cam': {'camera_fps': fps}}}, {'cam': {}}, {'cam': 999}, 1000))

    def test_valid_passes(self):
        self.assertEqual(check.assess({'cameras': {'cam': {'camera_fps': 5}}}, {'cam': {}}, {'cam': 990}, 1000), [])

    def test_disabled_camera_and_recording(self):
        self.assertEqual(check.assess({'cameras': {'cam': {'camera_fps': 5}}},
                                     {'cam': {'record': {'enabled': False}}, 'off': {'enabled': False}}, {}, 1000), [])
