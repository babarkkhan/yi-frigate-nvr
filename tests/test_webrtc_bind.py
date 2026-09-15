import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('webrtc_bind', Path(__file__).resolve().parents[1] / 'services/nvr/config/live-talk/prepare_webrtc.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WebRTCBindTests(unittest.TestCase):
    def test_refreshes_container_ip_without_changing_streams_or_public_candidates(self):
        original = {'streams': {'cam': ['source']}, 'api': {'listen': ':1984'},
                    'webrtc': {'candidates': ['203.0.113.10:8555'], 'filters': {'candidates': [], 'networks': ['tcp4'], 'ips': ['172.18.0.2']}}}
        expected = copy.deepcopy(original)
        expected['webrtc']['filters']['ips'] = ['172.18.0.9']
        self.assertEqual(module.bind_container_address(original, '172.18.0.9'), expected)

    def test_rejects_non_routable_or_invalid_addresses(self):
        for value in ['127.0.0.1', '0.0.0.0', '224.0.0.1', '::1', 'invalid']:
            with self.assertRaises(ValueError):
                module.bind_container_address({}, value)


if __name__ == '__main__':
    unittest.main()
