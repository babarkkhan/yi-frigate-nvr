#!/usr/bin/env python3
"""Resolve expected dimensions for this repo's full and GPU-scaled live streams.

Run inside Frigate: python3 - STREAM < scripts/live-stream-dimensions.py
Unknown transforms fail instead of validating output against its own probe.
"""
import json
from pathlib import Path
import re
import sys


def dimensions(config, stream):
    sources = config.get('go2rtc', {}).get('streams', {}).get(stream)
    if not sources:
        raise ValueError(f'No configured stream: {stream}')
    if stream in config.get('cameras', {}):
        d = config['cameras'][stream]['detect']
        return int(d['width']), int(d['height'])
    source = sources[0] if isinstance(sources, list) else sources
    parent = re.match(r'^ffmpeg:([^#]+)#', source)
    scale = re.search(r'(?:^|[ ,])scale_cuda=(\d+):(-?\d+)(?:$|[# ,])', source)
    if not parent or not scale or parent[1] not in config['cameras']:
        raise ValueError(f'Unknown dimensions/transform for {stream}')
    width, height = map(int, scale.groups())
    if width <= 0:
        raise ValueError('Invalid scale width')
    if height == -2:
        d = config['cameras'][parent[1]]['detect']
        height = int((width * int(d['height']) / int(d['width']) / 2) + .5) * 2
    if height <= 0:
        raise ValueError('Unsupported scale height')
    return width, height


if __name__ == '__main__':
    import yaml
    try:
        cfg = yaml.safe_load(Path('/config/config.yml').read_text())
        print(*dimensions(cfg, sys.argv[1]))
    except (OSError, KeyError, IndexError, ValueError, TypeError) as error:
        print(json.dumps({'error': str(error)}), file=sys.stderr)
        raise SystemExit(2)
