"""一次子进程运行的结局。"""

from __future__ import annotations

from typing import Optional


class RunResult:
    """`wproc.run()` 的返回值。

    Attributes:
        returncode: 子进程退出码；无法确定时为 ``None``。
        output: 子进程 stdout 与 stderr 合并后的原始字节。
        timed_out: 这次运行是否因为超出时间预算而被终止。
    """

    __slots__ = ("returncode", "output", "timed_out")

    def __init__(
        self,
        returncode: Optional[int] = None,
        output: bytes = b"",
        timed_out: bool = False,
    ) -> None:
        self.returncode = returncode
        self.output = output if output is not None else b""
        self.timed_out = bool(timed_out)

    @property
    def ok(self) -> bool:
        """正常结束且退出码为 0。"""
        return (not self.timed_out) and self.returncode == 0

    def text(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        """把 ``output`` 解码成字符串。"""
        return self.output.decode(encoding, errors)

    def __repr__(self) -> str:  # pragma: no cover - 诊断用
        return "RunResult(returncode=%r, timed_out=%r, output=%d bytes)" % (
            self.returncode,
            self.timed_out,
            len(self.output),
        )
