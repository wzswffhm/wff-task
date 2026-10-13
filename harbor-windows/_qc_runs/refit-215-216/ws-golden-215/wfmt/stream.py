"""容器的流式读取：不把整个文件读进内存。"""

from __future__ import annotations

import zlib

from .codec import ALIGN
from .crc import CRC_SIZE
from .errors import WFormatError
from .header import HEADER_SIZE, parse_header
from .varint import decode_uvarint

__all__ = ["CHUNK_SIZE", "iter_records", "read_all"]

#: 单次从底层文件对象请求的最大字节数。
CHUNK_SIZE = 4096


class _Window:
    """在底层文件对象之上维护一个定长窗口的读取器。

    只使用 ``read(n)``（``n`` 为正整数）向底层要数据，并增量维护已消费
    字节的 CRC，因此可以在不把整个容器读进内存的前提下校验尾部校验和。
    """

    def __init__(self, fileobj):
        self._f = fileobj
        self._buf = bytearray()
        self._eof = False
        self.crc = 0

    def _fill(self, need):
        while len(self._buf) < need and not self._eof:
            chunk = self._f.read(CHUNK_SIZE)
            if not chunk:
                self._eof = True
                break
            self._buf.extend(chunk)
        if len(self._buf) < need:
            raise WFormatError("truncated", "容器数据提前结束")

    def take(self, n, crc=True):
        """取出 ``n`` 字节；``crc=False`` 时不计入校验和。"""
        self._fill(n)
        out = bytes(self._buf[:n])
        del self._buf[:n]
        if crc:
            self.crc = zlib.crc32(out, self.crc)
        return out

    def take_uvarint(self):
        """按需逐字节读取一个 uvarint。"""
        shift = 0
        value = 0
        while True:
            byte = self.take(1)[0]
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value
            shift += 7
            if shift > 63:
                raise WFormatError("varint", "uvarint 超出 63 位")

    def drain(self):
        """返回尚未消费的剩余字节（用于读取尾部校验和之后的残留）。"""
        out = bytes(self._buf)
        self._buf.clear()
        while not self._eof:
            chunk = self._f.read(CHUNK_SIZE)
            if not chunk:
                self._eof = True
                break
            out += chunk
        return out


def iter_records(fileobj):
    """惰性地产出容器中的 ``(tag, payload)``。

    读取过程中不缓存整份数据；消费完最后一条记录后校验尾部 CRC，
    校验失败抛 ``WFormatError(kind="checksum")``。
    """
    window = _Window(fileobj)
    head = window.take(HEADER_SIZE)
    _version, count = parse_header(head)
    for _ in range(count):
        tag = window.take_uvarint()
        length = window.take_uvarint()
        payload = window.take(length)
        pad = (-(len(_encode_span(tag, length)) + length)) % ALIGN
        filler = window.take(pad)
        if any(filler):
            raise WFormatError("structure", "对齐填充必须为零字节")
        yield tag, payload
    stored = int.from_bytes(window.take(CRC_SIZE, crc=False), "little")
    if stored != (window.crc & 0xFFFFFFFF):
        raise WFormatError("checksum", "容器校验和不匹配")
    if window.drain():
        raise WFormatError("structure", "容器尾部存在多余数据")


def _encode_span(tag, length):
    """重算「tag + 长度域」的字节长度（不重新编码载荷）。"""
    from .varint import encode_uvarint

    return encode_uvarint(tag) + encode_uvarint(length)


def read_all(fileobj):
    """把惰性读取完整消费，返回 ``[(tag, payload), ...]``。"""
    return list(iter_records(fileobj))
