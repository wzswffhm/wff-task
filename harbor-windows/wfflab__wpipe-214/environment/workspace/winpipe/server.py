"""命名管道服务端。"""

from __future__ import annotations

from . import native
from .errors import WPipeError

__all__ = ["PipeServer"]


def _resolve_name(name):
    """把 ``foo`` 形态补全为 ``\\\\.\\pipe\\foo``。"""
    if isinstance(name, str) and name.startswith(native.PIPE_PREFIX):
        return name
    return native.PIPE_PREFIX + str(name)


class PipeServer:
    """把一个命名管道实例包装成可接受连接的『服务端』对象。

    参数
    ----
    name         管道名（``foo`` 或 ``\\\\.\\pipe\\foo`` 形式）。
    instances    允许的最大实例数。
    buffer_size  每次底层读写的缓冲区大小。
    message_mode 是否以「消息模式」创建管道（默认字节模式）。
    """

    def __init__(self, name, instances=1, buffer_size=4096, message_mode=False):
        self.name = name
        self.instances = instances
        self.buffer_size = buffer_size
        self.message_mode = message_mode
        self._handle = None

    # ------------------------------------------------------------ 生命周期
    def create_instance(self, first_instance=False):
        """创建服务端管道实例，返回句柄。"""
        handle = native.create_pipe(
            _resolve_name(self.name),
            instances=self.instances,
            buffer_size=self.buffer_size,
            message_mode=self.message_mode,
            first_instance=first_instance,
        )
        if not native.is_valid(handle):
            raise WPipeError("connection", "CreateNamedPipe failed for %r" % (self.name,),
                             winerror=native.last_error())
        self._handle = handle
        return handle

    def accept(self):
        """等待并接受一个客户端连接。"""
        ok = native.connect(self._handle)
        if not ok:
            raise WPipeError("connection", "ConnectNamedPipe failed for %r" % (self.name,),
                             winerror=native.last_error())
        return True

    # ------------------------------------------------------------ 数据面
    def read_frame(self):
        """读取一条完整的应用层消息。"""
        return native.read(self._handle, self.buffer_size)

    def write_frame(self, payload):
        """发送一条应用层消息。"""
        return native.write(self._handle, payload)

    def read_raw(self):
        """读取一段原始字节（不分帧）。"""
        return native.read(self._handle, self.buffer_size)

    def write_raw(self, data):
        """写入一段原始字节（不分帧）。"""
        return native.write(self._handle, data)

    def pending_bytes(self):
        """返回管道中当前可读的字节数（不消费）。"""
        return native.peek(self._handle)

    def close(self):
        """断开并关闭服务端实例（幂等）。"""
        if self._handle is not None:
            native.disconnect(self._handle)
            native.close(self._handle)
            self._handle = None
