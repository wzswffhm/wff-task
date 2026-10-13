"""The image checksum recorded in the optional header.

The value is exposed through a one-shot helper and through an incremental
accumulator, so a caller that already walks the file once can reuse the pass.
"""

import struct

from .errors import WImgError
from .headers import CHECKSUM_OFFSET, read_dos_header, read_file_header


class ChecksumAccumulator(object):
    """Incremental helper for the checksum of a byte stream."""

    def __init__(self):
        self._total = 0
        self._pending = b""

    def update(self, chunk):
        """Fold ``chunk`` into the running state and return ``self``."""
        buffer = self._pending + bytes(chunk)
        whole = len(buffer) - (len(buffer) % 4)
        for offset in range(0, whole, 4):
            self._total += struct.unpack_from("<I", buffer, offset)[0]
            self._total = (self._total & 0xFFFFFFFF) + (self._total >> 32)
        self._pending = buffer[whole:]
        return self

    def value(self, total_length):
        """Return the checksum of everything fed so far.

        ``total_length`` is the number of bytes the image occupies; it is
        folded in after the byte sum, exactly as the loader does.
        """
        tail = self._pending
        extra = 0
        for shift in range(len(tail)):
            extra |= tail[shift] << (8 * shift)
        total = self._total + extra
        total = (total & 0xFFFF) + (total >> 16)
        total = (total & 0xFFFF) + (total >> 16)
        return (total + total_length) & 0xFFFFFFFF


def checksum_field_offset(data):
    """Return where the CheckSum field sits, or ``None`` when it is absent."""
    try:
        nt_offset = read_dos_header(data)
        file_header = read_file_header(data, nt_offset)
    except WImgError:
        return None
    offset = file_header["optional_offset"] + CHECKSUM_OFFSET
    if offset + 4 > len(data):
        return None
    return offset


def compute_checksum(data):
    """Return the checksum of ``data``.

    The four bytes of the recorded value itself count as zero.
    """
    raw = bytes(data)
    masked = bytearray(raw)
    offset = checksum_field_offset(raw)
    if offset is not None:
        masked[offset:offset + 4] = b"\0\0\0\0"
    accumulator = ChecksumAccumulator()
    accumulator.update(bytes(masked))
    return accumulator.value(len(raw))


def stored_checksum(data, optional_offset):
    """Return the checksum currently recorded in the optional header."""
    return struct.unpack_from("<I", data, optional_offset + 64)[0]
