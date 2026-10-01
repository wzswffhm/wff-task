"""``wproc.run()``：时间预算、输出收集与结果封装。

反例变体 negative_01_kill_only_direct_child：
只修「输出保留」这一半 —— 用独立线程持续收输出、主线程只等直接子进程结束；
终止手段原样保留 ``proc.kill()``，后代进程失控。
"""

from __future__ import annotations

import subprocess
import threading
from typing import Mapping, Optional, Sequence, Union

from . import processes
from .errors import CommandFailed, CommandNotStarted, CommandTimedOut
from .results import RunResult

Command = Union[Sequence[str], "list[str]"]

_CHUNK = 65536
_DRAIN_GRACE_SEC = 0.5


def _drain(proc: subprocess.Popen, sink: bytearray, finished: threading.Event) -> None:
    stream = proc.stdout
    while True:
        chunk = stream.read1(_CHUNK)
        if not chunk:
            break
        sink.extend(chunk)
    finished.set()


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

    sink = bytearray()
    finished = threading.Event()
    reader = threading.Thread(target=_drain, args=(proc, sink, finished), daemon=True)
    reader.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        processes.terminate_process(proc)

    finished.wait(_DRAIN_GRACE_SEC)
    result = RunResult(returncode=proc.returncode, output=bytes(sink), timed_out=timed_out)
    if check:
        if timed_out:
            raise CommandTimedOut(timeout, result)
        if result.returncode != 0:
            raise CommandFailed(result)
    return result
