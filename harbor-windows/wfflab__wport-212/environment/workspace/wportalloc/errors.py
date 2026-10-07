"""wportalloc 的异常体系。"""


class WPortAllocError(Exception):
    """统一错误基类。``kind`` 标记出错的环节（如 "probe"）。"""

    def __init__(self, kind, *, port=None, host=None, message=None):
        self.kind = kind
        self.port = port
        self.host = host
        super().__init__(message or "wportalloc %s error (host=%r, port=%r)" % (kind, host, port))


class PortInUseError(WPortAllocError):
    """端口已被占用：绑定失败于 WSAEADDRINUSE(10048) / WSAEACCES(10013)。"""

    def __init__(self, *, port=None, host=None, message=None):
        super().__init__("port_in_use", port=port, host=host, message=message)
