"""wportalloc —— Windows 服务端口池分配器。

对外承诺：
- ``is_port_free``：真实反映端口占用状态（不受对端 socket 选项影响）；
- ``allocate``：给出「独占」的监听 socket，绝不与存量服务静默共存；
- ``check_service``：在 Windows 的地址解析顺序下仍能探活。
"""

from .errors import PortInUseError, WPortAllocError
from .health import check_service
from .listener import allocate
from .probe import is_port_free

__all__ = [
    "WPortAllocError",
    "PortInUseError",
    "is_port_free",
    "allocate",
    "check_service",
]
