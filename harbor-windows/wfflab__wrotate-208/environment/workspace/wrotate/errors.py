"""wrotate 使用的异常类型。"""


class WRotateError(Exception):
    """本库所有异常的基类。"""


class RotationError(WRotateError):
    """轮转过程中出现不可恢复的错误。"""
