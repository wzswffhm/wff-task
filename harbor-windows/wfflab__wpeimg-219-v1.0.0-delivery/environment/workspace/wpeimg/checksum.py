"""The image checksum recorded in the optional header.

The value is exposed through a one-shot helper and through an incremental
accumulator, so a caller that already walks the file once can reuse the pass.
"""

import struct
import zlib


class ChecksumAccumulator(object):
    """Incremental helper for the checksum of a byte stream."""

    def __init__(self):
        self._state = 0

    def update(self, chunk):
        """Fold ``chunk`` into the running state and return ``self``."""
        self._state = zlib.crc32(bytes(chunk), self._state)
        return self

    def value(self, total_length):
        """Return the checksum of everything fed so far.

        ``total_length`` is the number of bytes the image occupies.
        """
        return self._state & 0xFFFFFFFF


def compute_checksum(data):
    """Return the checksum of ``data``."""
    accumulator = ChecksumAccumulator()
    accumulator.update(data)
    return accumulator.value(len(data))


def stored_checksum(data, optional_offset):
    """Return the checksum currently recorded in the optional header."""
    return struct.unpack_from("<I", data, optional_offset + 64)[0]
