"""Look for trailing-zero padding and zero-length NALs in an Annex-B capture.

For upstream yi-hack-MStar #593. The MP4 demuxer error 'Invalid NAL unit size
(0 > N)' means an AVCC length prefix of zero, so the question is what in the
Annex-B source turns into a zero-length unit.
"""
import sys
from collections import Counter

data = open(sys.argv[1], 'rb').read()
starts, i, n = [], 0, len(data)
while i < n - 3:
    if data[i:i+4] == b'\x00\x00\x00\x01':
        starts.append((i, 4)); i += 4
    elif data[i:i+3] == b'\x00\x00\x01':
        starts.append((i, 3)); i += 3
    else:
        i += 1

print("file=%s  bytes=%d  start_codes=%d" % (sys.argv[1], n, len(starts)))

trailing = Counter()
empty = 0
examples = []
for idx, (pos, plen) in enumerate(starts):
    end = starts[idx+1][0] if idx+1 < len(starts) else n
    payload = data[pos+plen:end]
    if len(payload) == 0:
        empty += 1
        continue
    t = payload[0] & 0x1F
    # count trailing zero bytes on this NAL
    z = 0
    while z < len(payload) and payload[len(payload)-1-z] == 0:
        z += 1
    if z:
        trailing[(t, z)] += 1
        if len(examples) < 8:
            examples.append((pos, t, len(payload), z, payload[-min(12,len(payload)):].hex(' ')))

print("zero-length NALs (start code immediately followed by another): %d" % empty)
print("\nNALs ending in zero bytes  (type, trailing_zeros) -> count")
for (t, z), c in sorted(trailing.items(), key=lambda kv: -kv[1])[:12]:
    print("   type=%-3d trailing_zeros=%-4d count=%d" % (t, z, c))
if not trailing:
    print("   none")

print("\nexamples (offset, type, len, trailing_zeros, last bytes):")
for e in examples:
    print("   off=%-9d type=%-3d len=%-6d z=%-4d ...%s" % e)

# How many 00 00 00 00 runs (4+ zeros) exist overall?
runs, run, longest = 0, 0, 0
for b in data:
    if b == 0:
        run += 1
        longest = max(longest, run)
    else:
        if run >= 4:
            runs += 1
        run = 0
print("\nruns of >=4 consecutive zero bytes: %d   longest zero run: %d" % (runs, longest))
