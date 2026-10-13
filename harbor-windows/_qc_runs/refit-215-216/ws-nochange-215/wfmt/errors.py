"""wfmt 的错误类型。"""

from __future__ import annotations

__all__ = ["WFormatError"]


class WFormatError(Exception):
    """容器读写过程中的可分类错误。

    参数
    ----
    kind    错误类别字符串（如 ``"magic"`` / ``"checksum"`` / ``"truncated"``
            / ``"varint"`` / ``"structure"``）。
    message 人类可读描述；缺省时使用 ``kind``。
    """

    def __init__(self, kind, message=None, **details):
        self.kind = kind
        self.details = details
        super().__init__(message or str(kind))
