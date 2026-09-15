"""Resolve the current Docker IPv4 for ICE even when Tailscale is already up."""
import ipaddress
from pathlib import Path
import socket
import yaml


def bind_container_address(config, address):
    address = ipaddress.IPv4Address(address)
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        raise ValueError("Expected the container's routed IPv4 address")
    config.setdefault("webrtc", {}).setdefault("filters", {})["ips"] = [str(address)]
    return config


def main():
    path = Path("/dev/shm/go2rtc.yaml")
    config = yaml.safe_load(path.read_text())
    bind_container_address(config, socket.gethostbyname(socket.gethostname()))
    path.write_text(yaml.safe_dump(config, sort_keys=False))


if __name__ == "__main__":
    main()
