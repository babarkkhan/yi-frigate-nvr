#!/usr/bin/env python3
"""Stream go2rtc G.711 A-law input to a restricted Yi speaker SSH command.

No HTTP endpoint, no buffering into messages and no automatic delivery retries.
The pinned Frigate image supplies Python 3.11/audioop and cryptography 44.0.3.
Additional SSH packages live only in the private vendor directory.
"""
import argparse
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


def credentials_path(camera):
    if camera not in ("cam1", "cam2", "cam3", "cam4", "cam5", "cam6"):
        raise ValueError("unknown camera")
    # Retain the original cam1 credentials so its validated deployment is intact.
    return PRIVATE if camera == "cam1" else PRIVATE / camera


def main(camera="cam1"):
    private = credentials_path(camera)
    config = json.loads((private / "bridge.json").read_text())
    client = paramiko.SSHClient()
    client.load_host_keys(str(private / "known_hosts"))
    # Default RejectPolicy: never trust a changed/new camera host key silently.
    key = paramiko.RSAKey.from_private_key_file(str(private / "speaker_key"))
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("camera", nargs="?", default="cam1", choices=[f"cam{i}" for i in range(1, 7)])
    raise SystemExit(main(parser.parse_args().camera))
