"""wsync 的异常类型。

调用方可以只捕获 :class:`SyncError` 来处理所有预期内的同步失败。
"""

from __future__ import annotations

__all__ = ["SyncError", "TargetInUseError", "SourceTargetCollisionError"]


class SyncError(Exception):
    """wsync 所有可预期异常的基类。"""


class TargetInUseError(SyncError):
    """目标路径被其它进程占用，当前无法更新或删除。"""


class SourceTargetCollisionError(SyncError):
    """一条复制计划里源与目标指向同一个文件；继续执行会破坏数据。"""
