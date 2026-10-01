"""wjob 使用的异常类型。"""


class WJobError(Exception):
    """本库所有异常的基类。"""


class PowerShellError(WJobError):
    """PowerShell 无法启动或返回了不可用的结果。"""
