"""Parse SEI (NAL type 6) units and check their internal length fields.

For upstream yi-hack-MStar #593. SEI syntax: repeated { payload_type (0xFF*n +
last), payload_size (0xFF*n + last), payload[payload_size] } then
rbsp_trailing_bits (0x80). A payload_size that disagrees with the actual NAL
length is a concrete malformation.
"""
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

seis, bad = [], 0
for idx, (pos, plen) in enumerate(starts):
    end = starts[idx+1][0] if idx+1 < len(starts) else n
    pay = data[pos+plen:end]
    if pay and (pay[0] & 0x1F) == 6:
        seis.append((pos, pay))

print("SEI units found: %d" % len(seis))
for k, (pos, pay) in enumerate(seis[:5]):
    print("\n--- SEI #%d at offset %d, NAL length %d ---" % (k, pos, len(pay)))
    print("    raw: %s" % pay[:32].hex(' '))
    p = 1                                    # skip NAL header
    while p < len(pay):
        ptype = 0
        while p < len(pay) and pay[p] == 0xFF:
            ptype += 255; p += 1
        if p >= len(pay): print("    TRUNCATED in payload_type"); bad += 1; break
        ptype += pay[p]; p += 1
        psize = 0
        while p < len(pay) and pay[p] == 0xFF:
            psize += 255; p += 1
        if p >= len(pay): print("    TRUNCATED in payload_size"); bad += 1; break
        psize += pay[p]; p += 1
        remain = len(pay) - p
        flag = "OK" if psize <= remain else "OVERRUNS NAL by %d" % (psize - remain)
        print("    payload_type=%-5d payload_size=%-6d bytes_remaining=%-6d %s"
              % (ptype, psize, remain, flag))
        if psize > remain:
            bad += 1
            break
        p += psize
        if p < len(pay) and pay[p] == 0x80:
            print("    rbsp_trailing_bits 0x80 at end: OK")
            break
        if p >= len(pay):
            print("    ends with NO rbsp_trailing_bits (0x80 missing)")
            bad += 1
            break

print("\nmalformed SEI in the sample inspected: %d" % bad)
