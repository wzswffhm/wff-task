"""子进程的启动与结束。

反例变体 negative_03_use_timeout_expired_output（差一步）：
终止侧已修好（``taskkill /F /T`` 连后代一起杀），失手点只在 runner 的等待方式。
"""

from __future__ import annotations

import os
import subprocess
from typing import Mapping, Optional, Sequence

Command = Sequence[str]

_KILL_TIMEOUT_SEC = 60.0


def start_process(
    command: Command,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.Popen:
    """启动一个子进程，把 stdout 与 stderr 合并到同一个管道里。"""
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return subprocess.Popen(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )


def _kill_tree(pid: int) -> bool:
    try:
        completed = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(int(pid))],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_KILL_TIMEOUT_SEC,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def terminate_process(proc: subprocess.Popen) -> None:
    """结束一个子进程及其后代。"""
    if proc.poll() is None:
        if os.name == "nt":
            _kill_tree(proc.pid)
        if proc.poll() is None:
            proc.kill()
    proc.wait()
