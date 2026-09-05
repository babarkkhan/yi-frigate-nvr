"""Characterise H.264 NAL units in an Annex-B capture.

Written for upstream yi-hack-MStar issue #593: rtsp_server_yi on MStar emits
AUD (type 9) and Filler (type 12) units that break Annex-B -> AVCC conversion
when muxed to MP4, while decoding fine live.
"""
import sys
from collections import defaultdict

data = open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/cap.h264', 'rb').read()
print("captured %d bytes" % len(data))

starts, i, n = [], 0, len(data)
while i < n - 3:
    if data[i:i+4] == b'\x00\x00\x00\x01':
        starts.append((i, 4)); i += 4
    elif data[i:i+3] == b'\x00\x00\x01':
        starts.append((i, 3)); i += 3
    else:
        i += 1

nals = []
for idx, (pos, plen) in enumerate(starts):
    end = starts[idx+1][0] if idx+1 < len(starts) else n
    nals.append((pos, plen, data[pos+plen:end]))

NAMES = {1: 'non-IDR', 5: 'IDR', 6: 'SEI', 7: 'SPS', 8: 'PPS', 9: 'AUD', 12: 'FILLER'}
stat = defaultdict(lambda: [0, 0, set(), 0, 0])  # count, bytes, prefixes, tiny, zero_f
for pos, plen, payload in nals:
    if not payload:
        continue
    t = payload[0] & 0x1F
    s = stat[t]
    s[0] += 1
    s[1] += len(payload)
    s[2].add(plen)
    if len(payload) <= 1:
        s[3] += 1
    if payload[0] & 0x80:          # forbidden_zero_bit must be 0
        s[4] += 1

print("\n%-5s %-8s %7s %10s %8s %-11s %9s %9s" %
      ("type", "name", "count", "bytes", "avg", "startcode", "len<=1B", "fzb!=0"))
for t in sorted(stat):
    c, b, pl, tiny, fz = stat[t]
    print("%-5d %-8s %7d %10d %8.1f %-11s %9d %9d" %
          (t, NAMES.get(t, '?'), c, b, b / c, ",".join(str(x) for x in sorted(pl)), tiny, fz))

for target in (9, 12):
    ex = [(p, pl, pay) for p, pl, pay in nals if pay and (pay[0] & 0x1F) == target]
    print("\n--- type %d (%s): %d units ---" % (target, NAMES.get(target, '?'), len(ex)))
    for p, pl, pay in ex[:6]:
        print("  off=%-8d startcode=%dB payload_len=%-4d bytes=%s"
              % (p, pl, len(pay), pay[:16].hex(' ')))
