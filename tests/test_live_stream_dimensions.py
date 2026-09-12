import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('dimensions', Path(__file__).resolve().parents[1] / 'scripts/live-stream-dimensions.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DimensionTests(unittest.TestCase):
    def config(self, height):
        return {'cameras': {'cam': {'detect': {'width': 1920, 'height': height}}},
                'go2rtc': {'streams': {'cam': ['rtsp://192.0.2.1/main'],
                                      'cam_mobile': ['ffmpeg:cam#video=mobile#raw=-vf scale_cuda=960:-2']}}}

    def test_mstar_preserves_aspect_ratio(self):
        self.assertEqual(module.dimensions(self.config(1088), 'cam_mobile'), (960, 544))

    def test_allwinner_preserves_aspect_ratio(self):
        self.assertEqual(module.dimensions(self.config(1080), 'cam_mobile'), (960, 540))

    def test_full_resolution(self):
        self.assertEqual(module.dimensions(self.config(1088), 'cam'), (1920, 1088))

    def test_missing_stream_fails(self):
        with self.assertRaises(ValueError): module.dimensions(self.config(1080), 'missing')

    def test_unknown_transform_fails(self):
        config = self.config(1080)
        config['go2rtc']['streams']['cam_mobile'] = ['ffmpeg:cam#video=h264']
        with self.assertRaises(ValueError): module.dimensions(config, 'cam_mobile')


if __name__ == '__main__': unittest.main()
