"""wsafename 使用的异常类型。"""


class WSafeNameError(Exception):
    """本库所有异常的基类。"""


class InvalidNameError(WSafeNameError):
    """名称在 Windows 目标文件系统上不可用。"""


class NameTooLongError(InvalidNameError):
    """单个路径段的长度超过目标文件系统允许的上限。"""


class CollisionError(WSafeNameError):
    """两个不同的输入名称会落到同一个磁盘条目上。"""
