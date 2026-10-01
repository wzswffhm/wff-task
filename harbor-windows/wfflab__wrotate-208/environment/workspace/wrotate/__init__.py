"""wrotate —— 日志文件的序号轮转。

服务每天（或每达到一定大小）把 ``app.log`` 滚成 ``app.log.1``，并把已有轮转
依次后移，最后按保留份数删掉最老的。
"""

from . import fsutil
from .errors import RotationError, WRotateError
from .rotator import Rotator

__version__ = "1.5.2"

__all__ = [
    "RotationError",
    "Rotator",
    "WRotateError",
    "fsutil",
]
