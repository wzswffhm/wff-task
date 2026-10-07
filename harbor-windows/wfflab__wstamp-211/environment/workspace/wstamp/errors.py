"""wstamp 的统一异常。"""


class WStampError(OSError):
    """带类别标记的 wstamp 错误。

    ``kind`` 取值：

    - ``"readonly"``：目标带有只读属性，写动作被 Windows 拒绝（WinError 5）。
    """

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind
