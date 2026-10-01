"""wexec 使用的异常类型。"""


class WExecError(Exception):
    """本库所有异常的基类。"""


class CommandNotFound(WExecError):
    """在 PATH 上找不到指定命令。"""
