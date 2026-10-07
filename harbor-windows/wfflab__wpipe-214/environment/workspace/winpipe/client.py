"""命名管道客户端。"""

from __future__ import annotations

from . import native
from .errors import WPipeError

__all__ = ["PipeClient"]


def _resolve_name(name):
    """把 ``foo`` 形态补全为 ``\\\\.\\pipe\\foo``。"""
    if isinstance(name, str) and name.startswith(native.PIPE_PREFIX):
        return name
    return native.PIPE_PREFIX + str(name)


class PipeClient:
    """命名管道客户端。

    参数
    ----
    name        管道名（``foo`` 或 ``\\\\.\\pipe\\foo`` 形式）。
    timeout_ms  连接等待预算（毫秒）。
    buffer_size 每次底层读写的缓冲区大小。
    """

    def __init__(self, name, timeout_ms=5000, buffer_size=4096):
        self.name = name
        self.timeout_ms = timeout_ms
        self.buffer_size = buffer_size
        self._handle = None

    # ------------------------------------------------------------ 生命周期
    def connect(self):
        """连接到服务端管道。"""
        handle = native.open_pipe(_resolve_name(self.name))
        if not native.is_valid(handle):
            raise WPipeError("connection", "cannot open %r" % (self.name,),
                             winerror=native.last_error())
        self._handle = handle
        return True

    # ------------------------------------------------------------ 数据面
    def send(self, payload):
        """发送一条应用层消息。"""
        return native.write(self._handle, payload)

    def send_bytes(self, data):
        """写入一段原始字节（不分帧）。"""
        return native.write(self._handle, data)

    def recv(self):
        """接收一条应用层消息。"""
        return native.read(self._handle, self.buffer_size)

    def recv_raw(self):
        """读取一段原始字节（不分帧）。"""
        return native.read(self._handle, self.buffer_size)

    def close(self):
        """关闭客户端句柄（幂等）。"""
        if self._handle is not None:
            native.close(self._handle)
            self._handle = None
