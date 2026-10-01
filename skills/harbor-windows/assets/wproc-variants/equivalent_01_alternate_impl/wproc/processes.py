"""子进程的启动与结束。

等价实现 equivalent_01_alternate_impl：
与参考解不同的 API 组合与调用顺序 —— 先按 pid 逐级尝试，
先用 ``check_output`` 走一遍再把失败原因吞掉，最后才落到 ``proc.kill()``。
可观察行为与参考解一致。
"""

from __future__ import annotations

import os
import subprocess
from typing import Mapping, Optional, Sequence

Command = Sequence[str]

_KILL_TIMEOUT_SEC = 45.0


def start_process(
    command: Command,
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> subprocess.Popen:
    """启动一个子进程，把 stdout 与 stderr 合并到同一个管道里。"""
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    return subprocess.Popen(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )


def _try_taskkill(pid: int) -> bool:
    """整树终止；返回是否真的拿到成功退出码。"""
    try:
        subprocess.check_output(
            ["taskkill", "/f", "/t", "/pid", "%d" % int(pid)],
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=_KILL_TIMEOUT_SEC,
        )
    except subprocess.CalledProcessError:
        return False
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def terminate_process(proc: subprocess.Popen) -> None:
    """结束一个子进程。

    调用返回后 ``proc`` 一定已经退出，``proc.returncode`` 可用。
    """
    if proc.poll() is None and os.name == "nt":
        _try_taskkill(proc.pid)
    if proc.poll() is None:
        proc.kill()
    proc.wait()
