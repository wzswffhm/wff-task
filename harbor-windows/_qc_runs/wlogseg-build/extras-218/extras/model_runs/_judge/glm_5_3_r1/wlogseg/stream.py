"""流式读取。

流式读取与 :func:`wlogseg.unpack` 共用 :func:`wlogseg.codec.scan` 这一套
惰性扫描器：只通过固定大小的 ``read(n)``（``n`` 为正整数）向文件对象索要
数据，绝不整体读取，因此可以解析比内存大的容器。
"""

from __future__ import annotations

import io

from .codec import scan
from .errors import WSegError


def _coerce_handle(handle):
    """接受文件对象；也宽容地接受现成的字节串。"""
    if isinstance(handle, (bytes, bytearray, memoryview)):
        return io.BytesIO(bytes(handle))
    if not hasattr(handle, "read"):
        raise WSegError(
            "structure",
            f"expected an object with a read(n) method, got {type(handle).__name__}",
        )
    return handle


def iter_segments(handle):
    """惰性产出 (seg_id, payload)。

    段按文件顺序产出；容器只会被以固定大小的 ``read(n)`` 读取，不会整体装进
    内存。取完最后一段之后仍会校验尾部索引与尾部校验和，因此要把迭代器迭代
    到底（或交给 :func:`read_all`）才能发现完整性问题。
    """
    return scan(_coerce_handle(handle))


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return list(iter_segments(handle))
