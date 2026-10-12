"""``wproc.run()``：时间预算、输出收集与结果封装。

等价实现 equivalent_01_alternate_impl：
  * 用 ``poll()`` + 自算剩余预算的轮询循环等结束（不用 ``wait(timeout)``）
  * 用 ``os.read`` 在原始 fd 上收输出（不用 ``read1`` 包装）
  * 用 ``list`` + ``b"".join`` 组装（不用 ``bytearray``）
控制流与 API 均不同，但「先收输出、独立等结束、再判超时」的事实划分一致。
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Mapping, Optional, Sequence, Union

from . import processes
from .errors import CommandFailed, CommandNotStarted, CommandTimedOut
from .results import RunResult

Command = Union[Sequence[str], "list[str]"]

_READ_SIZE = 8192
_POLL_INTERVAL = 0.02
_DRAIN_GRACE_SEC = 0.5


def _reader(fd: int, chunks: list, done: threading.Event) -> None:
    try:
        while True:
            data = os.read(fd, _READ_SIZE)
            if not data:
                break
            chunks.append(data)
    except OSError:
        pass
    finally:
        done.set()


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

    chunks: list = []
    done = threading.Event()
    threading.Thread(
        target=_reader, args=(proc.stdout.fileno(), chunks, done), daemon=True
    ).start()

    deadline = None if timeout is None else time.monotonic() + float(timeout)
    timed_out = False
    while proc.poll() is None:
        if deadline is not None and time.monotonic() >= deadline:
            timed_out = True
            processes.terminate_process(proc)
            break
        time.sleep(_POLL_INTERVAL)

    done.wait(_DRAIN_GRACE_SEC)
    result = RunResult(
        returncode=proc.returncode, output=b"".join(chunks), timed_out=timed_out
    )
    if check:
        if timed_out:
            raise CommandTimedOut(timeout, result)
        if result.returncode != 0:
            raise CommandFailed(result)
    return result
