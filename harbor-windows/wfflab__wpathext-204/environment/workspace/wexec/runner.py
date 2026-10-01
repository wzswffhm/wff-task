"""运行已经解析出来的命令。"""

import subprocess

from .resolve import resolve


def run(argv, timeout=None):
    """解析 ``argv[0]`` 并执行，返回 ``subprocess.CompletedProcess``。"""
    if not argv:
        raise ValueError("argv must not be empty")

    path = resolve(argv[0])
    return subprocess.run(
        [path] + [str(a) for a in argv[1:]],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_ok(argv, timeout=None):
    """执行并断言成功；返回标准输出（已去掉尾部空白）。"""
    proc = run(argv, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            "command %r exited with %d: %s" % (argv[0], proc.returncode, proc.stderr.strip())
        )
    return proc.stdout.strip()
