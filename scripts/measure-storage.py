#!/usr/bin/env python3
"""Small buffered+fsync application I/O sample, not a raw disk benchmark.

Inside Frigate: python3 - < scripts/measure-storage.py
Writes at most 64 MiB + 128 KiB per path in a unique temporary directory,
then removes only its own files. No recording/database files are opened.
No cache eviction, direct I/O, full-disk test or throughput saturation.
"""
import json
import os
from pathlib import Path
import shutil
import statistics
import tempfile
import time


def sample(root):
    if shutil.disk_usage(root).free < 2 * 1024**3:
        raise RuntimeError('Less than 2 GiB free; refusing sample')
    block = os.urandom(4 * 1024**2)
    sync_ms = []
    deadline = time.monotonic() + 30
    with tempfile.TemporaryDirectory(prefix='.nvr-io-probe-', dir=root) as tmp:
        path = Path(tmp)/'payload'
        started = time.monotonic()
        with path.open('wb', buffering=0) as f:
            for _ in range(16):
                if time.monotonic() > deadline:
                    raise TimeoutError('I/O exceeded 30-second soft budget')
                tick = time.monotonic()
                f.write(block)
                os.fsync(f.fileno())
                sync_ms.append((time.monotonic()-tick)*1000)
        write_s = time.monotonic()-started
        tick = time.monotonic()
        with path.open('rb', buffering=0) as f:
            read_bytes = 0
            while data := f.read(len(block)):
                read_bytes += len(data)
        read_s = time.monotonic()-tick
        metadata_ms = []
        for i in range(32):
            if time.monotonic() > deadline:
                raise TimeoutError('I/O exceeded 30-second soft budget')
            tick = time.monotonic()
            item = Path(tmp)/f'meta-{i}'
            with item.open('xb', buffering=0) as f:
                f.write(block[:4096])
                os.fsync(f.fileno())
            renamed = item.with_suffix('.done')
            item.rename(renamed)
            renamed.unlink()
            metadata_ms.append((time.monotonic()-tick)*1000)
        return {'path': root, 'write_mib': 64, 'write_fsync_mib_s': round(64/write_s, 2),
                'write_fsync_ms_median': round(statistics.median(sync_ms), 2),
                'write_fsync_ms_max': round(max(sync_ms), 2),
                'warm_read_mib_s': round(read_bytes/1024**2/read_s, 2),
                'metadata_ms_median': round(statistics.median(metadata_ms), 2),
                'metadata_ms_max': round(max(metadata_ms), 2)}


if __name__ == '__main__':
    failed = False
    for root in ('/media/frigate', '/config', '/tmp'):
        try:
            print(json.dumps(sample(root)), flush=True)
        except Exception as error:
            failed = True
            print(json.dumps({'path': root, 'error': str(error)}), flush=True)
    raise SystemExit(1 if failed else 0)
