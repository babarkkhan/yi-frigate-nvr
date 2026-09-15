"""Offline contract tests; never connect to a camera or read a microphone."""
import audioop
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location('bridge', Path(__file__).resolve().parents[1] / 'services/nvr/config/live-talk/speaker_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class SpeakerBridgeTests(unittest.TestCase):
    def run_bridge(self, data, connect_error=None, status=0):
        client = MagicMock()
        channel = client.get_transport.return_value.open_session.return_value
        channel.exit_status_ready.return_value = False
        channel.shutdown_write.side_effect = lambda: setattr(channel.exit_status_ready, 'return_value', True)
        channel.recv_exit_status.return_value = status
        if connect_error:
            client.connect.side_effect = connect_error
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryFile() as source:
            private = Path(tmp)
            (private / 'bridge.json').write_text(json.dumps({'host': 'camera.invalid'}))
            source.write(data)
            source.seek(0)
            stdin = MagicMock(buffer=source)
            stdin.fileno.return_value = source.fileno()
            log = io.StringIO()
            with patch.object(bridge, 'PRIVATE', private), patch.object(bridge.paramiko, 'SSHClient', return_value=client), patch.object(bridge.paramiko.RSAKey, 'from_private_key_file', return_value=object()), patch.object(bridge.sys, 'stdin', stdin), contextlib.redirect_stderr(log):
                result = bridge.main()
        sent = b''.join(call.args[0] for call in channel.sendall.call_args_list)
        return result, sent, client, channel, log.getvalue()

    def test_chunk_boundaries_preserve_audio_duration_and_samples(self):
        pcm = b''.join(struct.pack('<h', ((i % 80) - 40) * 300) for i in range(8000))
        alaw = audioop.lin2alaw(pcm, 2)
        expected, _ = audioop.ratecv(audioop.alaw2lin(alaw, 2), 2, 1, 8000, 16000, None)
        result, sent, client, channel, _ = self.run_bridge(alaw)
        self.assertEqual(result, 0)
        self.assertEqual(sent, expected)
        self.assertAlmostEqual(len(sent) / 32000, 1, places=3)
        self.assertGreater(channel.sendall.call_count, 1)
        self.assertFalse(client.connect.call_args.kwargs['allow_agent'])
        self.assertFalse(client.connect.call_args.kwargs['look_for_keys'])
        client.load_host_keys.assert_called_once()
        client.set_missing_host_key_policy.assert_not_called()
        channel.close.assert_called_once()

    def test_failed_connection_never_sends_or_retries_or_logs_details(self):
        result, sent, client, _, log = self.run_bridge(b'abc', RuntimeError('sensitive remote details'))
        self.assertEqual(result, 1)
        self.assertEqual(sent, b'')
        client.connect.assert_called_once()
        client.close.assert_called_once()
        self.assertNotIn('sensitive remote details', log)

    def test_camera_rejection_is_reported(self):
        result, _, client, channel, log = self.run_bridge(b'abc', status=75)
        self.assertEqual(result, 1)
        self.assertIn('failed', log)
        channel.close.assert_called_once()
        client.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
