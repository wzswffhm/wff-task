"""wproc —— 在 Windows 上受控地运行子进程。"""

from __future__ import annotations

from .errors import (
    CommandFailed,
    CommandNotStarted,
    CommandTimedOut,
    WProcError,
)
from .results import RunResult
from .runner import run

__all__ = [
    "run",
    "RunResult",
    "WProcError",
    "CommandFailed",
    "CommandTimedOut",
    "CommandNotStarted",
]

__version__ = "2.1.0"
