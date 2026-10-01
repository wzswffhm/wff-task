"""``wproc.run()``：时间预算、输出收集与结果封装。"""

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
    """运行一条命令，收集输出并在超出 ``timeout`` 秒时终止它。

    Args:
        command: 参数序列，例如 ``["python", "build.py"]``。不接受整串字符串。
        timeout: 挂钟预算，单位秒；``None`` 表示不限制。
        cwd: 子进程的工作目录。
        env: **替换**子进程的环境，而不是在父进程环境上追加。
        check: 为真且退出码非零时抛 :class:`CommandFailed`。

    Returns:
        :class:`RunResult`。
    """
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
    except subprocess.TimeoutExpired:
        processes.terminate_process(proc)
        result = RunResult(returncode=proc.returncode, output=b"", timed_out=True)
        if check:
            raise CommandTimedOut(timeout, result)
        return result

    result = RunResult(returncode=proc.returncode, output=output or b"")
    if check and result.returncode != 0:
        raise CommandFailed(result)
    return result
