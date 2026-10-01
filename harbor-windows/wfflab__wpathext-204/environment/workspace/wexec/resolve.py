"""在 PATH 上把命令名解析成磁盘路径。

Windows 上「命令名」通常不带扩展名，例如 ``where``、``git``、``build``。
Shell 之所以能找到它们，是因为按 :envvar:`PATHEXT` 里声明的扩展名顺序
逐个试探。任何要自己启动外部程序的工具都必须照做，否则只能看见 ``.exe``。
"""

import os

from .errors import CommandNotFound

#: 找不到 PATHEXT 时使用的兜底扩展名。
EXECUTABLE_EXTENSIONS = (".exe",)


def search_dirs():
    """返回 PATH 中需要搜索的目录列表。"""
    raw = os.environ.get("PATH", "")
    return [d for d in raw.split(os.pathsep) if d]


def executable_extensions():
    """返回按优先级排列的可执行扩展名。

    优先使用环境变量 :envvar:`PATHEXT`；它缺失时才退回内置兜底值。
    """
    return EXECUTABLE_EXTENSIONS


def resolve(name):
    """把 ``name`` 解析成磁盘上的绝对路径。

    找不到时抛 :class:`CommandNotFound`。
    """
    if not name:
        raise CommandNotFound(name)

    for directory in search_dirs():
        candidate = os.path.join(directory, "%s.exe" % name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    raise CommandNotFound(name)
