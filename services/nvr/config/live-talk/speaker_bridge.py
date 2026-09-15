#!/usr/bin/env python3
"""Stream go2rtc G.711 A-law input to a restricted Yi speaker SSH command.

No HTTP endpoint, no buffering into messages and no automatic delivery retries.
The pinned Frigate image supplies Python 3.11/audioop and cryptography 44.0.3.
Additional SSH packages live only in the private vendor directory.
"""
import audioop
import json
import os
from pathlib import Path
import select
import socket
import sys
import time

PRIVATE = Path(os.environ.get("NVR_TALK_PRIVATE", "/config/.live-talk"))
sys.path.insert(0, str(PRIVATE / "vendor"))
import paramiko


def main():
    config = json.loads((PRIVATE / "bridge.json").read_text())
    client = paramiko.SSHClient()
    client.load_host_keys(str(PRIVATE / "known_hosts"))
    # Default RejectPolicy: never trust a changed/new camera host key silently.
    key = paramiko.RSAKey.from_private_key_file(str(PRIVATE / "speaker_key"))
    channel = None
    total = 0
    try:
        client.connect(config["host"], port=config.get("port", 22), username="root",
                       pkey=key, look_for_keys=False, allow_agent=False,
                       timeout=5, auth_timeout=5, banner_timeout=5)
        transport = client.get_transport()
        transport.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        channel = transport.open_session(timeout=5)
        channel.settimeout(3)
        channel.exec_command("speaker")
        state = None
        deadline = time.monotonic() + min(120, config.get("max_seconds", 120))
        while time.monotonic() < deadline and not channel.exit_status_ready():
            if not select.select([sys.stdin.buffer], [], [], 0.25)[0]:
                continue
            data = os.read(sys.stdin.fileno(), 4096)
            if not data:
                break
            pcm = audioop.alaw2lin(data, 2)
            pcm, state = audioop.ratecv(pcm, 2, 1, 8000, 16000, state)
            channel.sendall(pcm)
            total += len(pcm)
        channel.shutdown_write()
        # Allow the tiny in-flight tail to drain, then always close the channel.
        end = time.monotonic() + 1
        while not channel.exit_status_ready() and time.monotonic() < end:
            time.sleep(0.02)
        if channel.exit_status_ready() and channel.recv_exit_status() != 0:
            raise RuntimeError("speaker rejected the session")
        print(json.dumps({"speaker": "stopped", "pcm_bytes": total}), file=sys.stderr)
        return 0
    except Exception as error:
        # Avoid logging credentials, addresses or remote response text.
        print(json.dumps({"speaker": "failed", "error": type(error).__name__, "pcm_bytes": total}), file=sys.stderr)
        return 1
    finally:
        if channel is not None:
            channel.close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
