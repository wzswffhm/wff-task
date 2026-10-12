"""wlogseg 的错误类型。"""

from __future__ import annotations


class WSegError(Exception):
    """容器结构或完整性错误，``kind`` 为契约定义的分类之一。"""

    KINDS = ("magic", "version", "truncated", "structure", "checksum")

    def __init__(self, kind: str, message: str = "") -> None:
        if kind not in self.KINDS:
            raise ValueError(f"unknown error kind: {kind!r}")
        super().__init__(message or kind)
        self.kind = kind
        self.message = message
