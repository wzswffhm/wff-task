"""wexec —— 可靠地查找并执行 Windows 上的外部命令。

构建工具链经常需要在 PATH 上按名字寻找工具：``msbuild``、``ninja``、
``clang-cl``…… 在 Windows 上它们未必是 ``.exe``，所以查找逻辑必须
遵循 :envvar:`PATHEXT` 的扩展名顺序。
"""

from .errors import CommandNotFound, WExecError
from .resolve import EXECUTABLE_EXTENSIONS, executable_extensions, resolve, search_dirs
from .runner import run, run_ok

__version__ = "3.2.1"

__all__ = [
    "CommandNotFound",
    "EXECUTABLE_EXTENSIONS",
    "WExecError",
    "executable_extensions",
    "resolve",
    "run",
    "run_ok",
    "search_dirs",
]
