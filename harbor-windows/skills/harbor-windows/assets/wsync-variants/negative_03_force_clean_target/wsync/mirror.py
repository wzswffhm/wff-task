"""执行同步计划。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from . import fsops
from .planner import CREATE, DELETE, KEEP, UPDATE, PlanEntry, build_plan


@dataclass
class SyncResult:
    """一次镜像同步的结果。

    ``created`` / ``updated`` / ``deleted`` / ``kept`` 记录已完成的相对
    路径；``failed`` 记录没有完成的条目，每一项形如::

        {"action": "delete", "relpath": "logs/app.old", "error": "..."}
    """

    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """没有任何条目失败时为 ``True``。"""
        return not self.failed


def _apply(entry: PlanEntry, target_root: str) -> None:
    if entry.action in (CREATE, UPDATE):
        # 同一条路径不能既是文件又是目录，且路径比较不区分大小写：
        # 落盘之前先把目标侧的挡路条目清掉。
        fsops.clear_target_path(target_root, entry.relpath)
        fsops.copy_file(entry.source, entry.target)
        try:
            fsops.set_mtime_like(entry.target, entry.source)
        except OSError:
            pass
    elif entry.action == DELETE:
        if not os.path.isfile(entry.target):
            # 该条目已在消解类型冲突时被一并清掉，同步结束后目标上确实不再有它。
            return
        fsops.remove_file(entry.target)


def _record(result: SyncResult, action: str, relpath: str) -> None:
    if action == CREATE:
        result.created.append(relpath)
    elif action == UPDATE:
        result.updated.append(relpath)
    elif action == DELETE:
        result.deleted.append(relpath)


def _align_kept_mtime(entry: PlanEntry) -> None:
    """内容已经一致、只有时间戳没对齐时，补上时间戳而不重写内容。"""
    try:
        if os.stat(entry.source).st_mtime_ns != os.stat(entry.target).st_mtime_ns:
            fsops.set_mtime_like(entry.target, entry.source)
    except OSError:
        pass


def sync_tree(source_root: str, target_root: str, dry_run: bool = False) -> SyncResult:
    """把 ``source_root`` 镜像同步到 ``target_root``。

    单个目标条目失败（例如被其它进程占用）不会中断整次同步：该条目会
    记入 :attr:`SyncResult.failed`，其余条目继续处理。
    """
    source_root = os.path.abspath(source_root)
    target_root = os.path.abspath(target_root)

    if not dry_run:
        os.makedirs(target_root, exist_ok=True)
        # 反例：不区分“该删的”和“该留的”，直接用清空目标目录来回避各种
        # 类型冲突与只读障碍。终态看着对，但保留语义被破坏、且不幂等。
        for name in os.listdir(target_root):
            victim = os.path.join(target_root, name)
            try:
                if os.path.isdir(victim):
                    fsops.remove_tree(victim)
                else:
                    fsops.remove_file(victim)
            except OSError:
                pass

    plan = build_plan(source_root, target_root)
    result = SyncResult()

    for entry in plan.entries:
        if entry.action == KEEP:
            result.kept.append(entry.relpath)
            if not dry_run:
                _align_kept_mtime(entry)
            continue
        if dry_run:
            _record(result, entry.action, entry.relpath)
            continue
        try:
            _apply(entry, target_root)
        except OSError as exc:
            result.failed.append(
                {"action": entry.action, "relpath": entry.relpath, "error": str(exc)}
            )
            continue
        _record(result, entry.action, entry.relpath)

    if not dry_run:
        fsops.prune_empty_dirs(target_root)

    return result
