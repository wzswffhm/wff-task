"""winpipe 的错误类型。

所有对外抛出的错误都是 ``WPipeError``（或它的子类），并用 ``kind``
字段标记错误类别：

- ``"name"``       —— 管道名不合法；
- ``"connection"`` —— 连接建立/握手失败；
- ``"busy"``       —— 目标管道实例全部被占用且等待超时。
"""

from __future__ import annotations

__all__ = ["WPipeError", "PipeBusyError"]


class WPipeError(Exception):
    """winpipe 领域错误。"""

    def __init__(self, kind: str, message: str | None = None, winerror: int | None = None):
        self.kind = kind
        self.winerror = winerror
        super().__init__(message or kind)


class PipeBusyError(WPipeError):
    """目标管道名下的所有实例都处于忙状态，且等待超时。"""

    def __init__(self, name: str, timeout_ms: int | None = None, winerror: int | None = None):
        self.name = name
        self.timeout_ms = timeout_ms
        super().__init__("busy", "no free pipe instance for %r" % (name,), winerror=winerror)
