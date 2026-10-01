"""wpublish 使用的异常类型。"""


class WPublishError(Exception):
    """本库所有异常的基类。"""


class ICaclsError(WPublishError):
    """底层 icacls 调用失败。"""
