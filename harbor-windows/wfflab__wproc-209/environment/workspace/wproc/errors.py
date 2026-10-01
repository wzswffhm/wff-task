"""wproc 的异常类型。"""

from __future__ import annotations

from typing import Optional


class WProcError(Exception):
    """wproc 所有异常的基类。"""


class CommandFailed(WProcError):
    """命令正常结束，但退出码非零。"""

    def __init__(self, result) -> None:
        self.result = result
        rc = getattr(result, "returncode", None)
        super().__init__("command failed with exit code %r" % (rc,))


class CommandTimedOut(WProcError):
    """命令超出时间预算，并且调用方要求以异常形式上报。"""

    def __init__(self, timeout: Optional[float], result=None) -> None:
        self.timeout = timeout
        self.result = result
        super().__init__("command exceeded its time budget of %r seconds" % (timeout,))


class CommandNotStarted(WProcError):
    """连进程都没能创建出来（例如可执行文件不存在）。"""
