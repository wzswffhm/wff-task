"""WCHK 容器的结构 / 完整性错误。

所有「结构或完整性」问题都必须抛 WChunkError，而不是泄漏 ValueError /
struct.error / IndexError；err.kind 用于分类（与 instruction.md 的 D 表一致）。
"""

from __future__ import annotations


class WChunkError(Exception):
    """WCHK 容器错误。kind ∈ {magic, version, truncated, structure, checksum}"""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - 仅用于调试输出
        return f"WChunkError(kind={self.kind!r}, message={self.message!r})"
