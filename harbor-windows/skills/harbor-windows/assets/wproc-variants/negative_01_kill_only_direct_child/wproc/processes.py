"""子进程的启动与结束。

把「如何在 Windows 上创建并结束一个子进程」集中在一处，
让 runner 只关心预算、输出与结果封装。
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

import subprocess

Command = Sequence[str]


def start_process(
    command: Command,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.Popen:
    """启动一个子进程，把 stdout 与 stderr 合并到同一个管道里。"""
    return subprocess.Popen(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def terminate_process(proc: subprocess.Popen) -> None:
    """结束一个子进程。

    调用返回后 ``proc`` 一定已经退出，``proc.returncode`` 可用。
    已经结束的进程不会被重复处理。
    """
    if proc.poll() is None:
        proc.kill()
    proc.wait()
