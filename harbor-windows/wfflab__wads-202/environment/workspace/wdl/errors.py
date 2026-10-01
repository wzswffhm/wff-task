"""wdl 使用的异常类型。"""


class WDLError(Exception):
    """本库所有异常的基类。"""


class StreamError(WDLError):
    """备用数据流读写失败。"""


class ArchiveError(WDLError):
    """归档过程失败。"""
