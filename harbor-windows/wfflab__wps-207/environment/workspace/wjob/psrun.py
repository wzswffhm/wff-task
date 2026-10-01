"""调用 PowerShell 执行脚本。

自动化流水线经常把一段 PowerShell 当作一个「步骤」来跑，并根据它的退出码
决定要不要继续。PowerShell 的退出码语义与 bash 不同：**非终止错误不会改变
退出码**，原生命令的退出码也只保存在 ``$LASTEXITCODE`` 里而不会自动成为
PowerShell 进程的退出码。要把一个步骤的成败如实带出来，必须显式处理。
"""

import os
import shutil
import subprocess

from .errors import PowerShellError
from .result import PSResult

#: PowerShell 可执行文件名。
POWERSHELL = "powershell.exe"

#: 兜底搜索用的可执行文件名。
FALLBACKS = ("pwsh.exe", "powershell")


def find_powershell():
    """返回可用的 PowerShell 可执行文件路径。"""
    found = shutil.which(POWERSHELL)
    if found:
        return found
    for name in FALLBACKS:
        found = shutil.which(name)
        if found:
            return found
    raise PowerShellError("no PowerShell executable found on PATH")


def _base_argv():
    return [
        find_powershell(),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
    ]


def run_script(script, timeout=None):
    """执行一段 PowerShell ``script``，返回 :class:`PSResult`。"""
    proc = subprocess.run(
        _base_argv() + ["-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return PSResult(exit_code=proc.returncode, stdout=proc.stdout, stderr="")


def run_file(path, timeout=None):
    """执行一个 ``.ps1`` 文件，返回 :class:`PSResult`。"""
    proc = subprocess.run(
        _base_argv() + ["-File", path],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return PSResult(exit_code=proc.returncode, stdout=proc.stdout, stderr="")


def environment_info():
    """返回执行环境的可读信息。"""
    return {
        "powershell": find_powershell(),
        "comspec": os.environ.get("COMSPEC", ""),
    }
