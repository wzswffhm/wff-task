"""winpipe —— Windows 命名管道（named pipe）服务框架。

对外提供 ``PipeServer``（服务端）与 ``PipeClient``（客户端）两个入口，
用于在同一台 Windows 主机的进程之间搬运带边界的分帧消息。
"""

from .client import PipeClient
from .errors import PipeBusyError, WPipeError
from .server import PipeServer

__all__ = ["PipeServer", "PipeClient", "WPipeError", "PipeBusyError"]
