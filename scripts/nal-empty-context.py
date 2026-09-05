"""Show the byte context around zero-length NAL units. Upstream #593."""
import sys
data = open(sys.argv[1], 'rb').read()
starts, i, n = [], 0, len(data)
while i < n - 3:
    if data[i:i+4] == b'\x00\x00\x00\x01':
        starts.append((i, 4)); i += 4
    elif data[i:i+3] == b'\x00\x00\x01':
        starts.append((i, 3)); i += 3
    else:
        i += 1

shown = 0
patterns = {}
for idx, (pos, plen) in enumerate(starts[:-1]):
    nxt = starts[idx+1][0]
    if nxt == pos + plen:                       # nothing between the two start codes
        prev_t = None
        if idx > 0:
            p0, pl0 = starts[idx-1]
            pay = data[p0+pl0:pos]
            if pay:
                prev_t = pay[0] & 0x1F
        nxt_pay = data[starts[idx+1][0]+starts[idx+1][1]:starts[idx+2][0]] if idx+2 < len(starts) else b''
        nxt_t = (nxt_pay[0] & 0x1F) if nxt_pay else None
        key = (plen, starts[idx+1][1], prev_t, nxt_t)
        patterns[key] = patterns.get(key, 0) + 1
        if shown < 5:
            lo = max(0, pos - 8)
            print("  offset=%-9d  bytes: %s  |  %s"
                  % (pos, data[lo:pos].hex(' '), data[pos:pos+10].hex(' ')))
            print("     empty NAL: %d-byte start code, next start code %d-byte; "
                  "preceded by NAL type %s, followed by type %s"
                  % (plen, starts[idx+1][1], prev_t, nxt_t))
            shown += 1

print("\npattern summary (this_sc_len, next_sc_len, prev_nal_type, next_nal_type) -> count")
for k, v in sorted(patterns.items(), key=lambda kv: -kv[1]):
    print("   %s -> %d" % (str(k), v))
