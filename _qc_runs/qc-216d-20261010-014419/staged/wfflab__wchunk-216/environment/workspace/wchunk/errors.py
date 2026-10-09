"""WCHK 容器的结构 / 完整性错误。

结构或完整性问题抛 WChunkError，err.kind 用于分类。
"""

from __future__ import annotations


class WChunkError(Exception):
    """WCHK 容器错误。kind ∈ {magic, version, truncated, structure, checksum}"""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover
        return f"WChunkError(kind={self.kind!r}, message={self.message!r})"
