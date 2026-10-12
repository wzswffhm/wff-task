"""``wproc.run()``：时间预算、输出收集与结果封装。

反例变体 negative_03_use_timeout_expired_output（差一步）：
进程树已能正确终止，超时分支改用 ``TimeoutExpired.output`` 兜住截止前的输出，
看上去「两项都修了」；但没有把「读输出」与「等结束」拆成两条独立事实 ——
直接子进程已退出、仅由后代持有输出管道时，仍会被判成超时。
"""

from __future__ import annotations

import subprocess
from typing import Mapping, Optional, Sequence, Union

from . import processes
from .errors import CommandFailed, CommandNotStarted, CommandTimedOut
from .results import RunResult

Command = Union[Sequence[str], "list[str]"]


def run(
    command: Command,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    check: bool = False,
) -> RunResult:
    """运行一条命令，收集输出并在超出 ``timeout`` 秒时终止它。"""
    if isinstance(command, (str, bytes)):
        raise TypeError("command must be a sequence of arguments, not a string")
    argv = [str(item) for item in command]
    if not argv:
        raise ValueError("command must not be empty")

    try:
        proc = processes.start_process(argv, cwd=cwd, env=env)
    except OSError as exc:
        raise CommandNotStarted(str(exc)) from exc

    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        processes.terminate_process(proc)
        partial = exc.output or b""
        if isinstance(partial, str):
            partial = partial.encode("utf-8", "replace")
        result = RunResult(returncode=proc.returncode, output=partial, timed_out=True)
        if check:
            raise CommandTimedOut(timeout, result)
        return result

    result = RunResult(returncode=proc.returncode, output=output or b"")
    if check and result.returncode != 0:
        raise CommandFailed(result)
    return result
