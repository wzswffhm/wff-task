"""wscan 的异常体系。"""


class WScanError(Exception):
    """统一错误基类。``kind`` 标记出错的环节。"""

    def __init__(self, kind, *, root=None, message=None):
        self.kind = kind
        self.root = root
        super().__init__(message or "wscan %s error (root=%r)" % (kind, root))
