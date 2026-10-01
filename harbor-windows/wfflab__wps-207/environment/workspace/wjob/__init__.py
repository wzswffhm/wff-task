"""wjob —— 把 PowerShell 脚本当作流水线步骤来执行。

流水线需要知道每一步到底成没成。PowerShell 的退出码语义与 shell 脚本差别很大，
直接启动它并读取返回码会得到错误结论。
"""

from .errors import PowerShellError, WJobError
from .psrun import (
    FALLBACKS,
    POWERSHELL,
    environment_info,
    find_powershell,
    run_file,
    run_script,
)
from .result import PSJob, PSResult

__version__ = "2.0.3"

__all__ = [
    "FALLBACKS",
    "POWERSHELL",
    "PSJob",
    "PSResult",
    "PowerShellError",
    "WJobError",
    "environment_info",
    "find_powershell",
    "run_file",
    "run_script",
]
