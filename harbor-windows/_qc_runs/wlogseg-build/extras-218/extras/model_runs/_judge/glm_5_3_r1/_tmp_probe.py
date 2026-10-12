import struct
import zlib

data = open('assets/sample.wlsg', 'rb').read()
empty = open('assets/sample_empty.wlsg', 'rb').read()

magic, ver, flags, count, idxoff, res = struct.unpack_from('<4sBBHII', data, 0)
print('magic', magic, 'ver', ver, 'flags', flags, 'count', count, 'idxoff', idxoff, 'res', res)

cursor = 16
segs = []
for i in range(count):
    sid, sf, r, blen = struct.unpack_from('<HBBI', data, cursor)
    total = 8 + blen
    pad = (-total) % 8
    total += pad
    segs.append((i, sid, blen, cursor, total, pad))
    cursor += total
print('walk end', cursor, '== idxoff?', cursor == idxoff)
for s in segs:
    print('  seg', s)

print('index entries:')
for i in range(count):
    print('  ', struct.unpack_from('<II', data, idxoff + 8 * i))
print('trailer', [hex(x) for x in struct.unpack_from('<II', data, len(data) - 8)])
print('crc(idx)       ', hex(zlib.crc32(data[idxoff:len(data) - 8])))
print('crc(hdr+segs)  ', hex(zlib.crc32(data[:idxoff])))

print('empty header', struct.unpack_from('<4sBBHII', empty, 0))
print('empty trailer', [hex(x) for x in struct.unpack_from('<II', empty, 16)])
print('crc(empty hdr)', hex(zlib.crc32(empty[:16])))
print('crc32 check value b"123456789" ->', hex(zlib.crc32(b'123456789')))
