"""执行同步计划（**等价对照实现**）。

与参考解的差别：
  - 用「动作 → 处理器」表派发，而不是 if/elif 链
  - 冲突清理与落盘合并进同一个 ``_write_entry``，没有单独的 ``_apply``
  - KEEP 条目在计划期之后统一做一次时间戳巡检
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from . import fsops
from .planner import CREATE, DELETE, KEEP, UPDATE, PlanEntry, build_plan


@dataclass
class SyncResult:
    """一次镜像同步的结果。"""

    created: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)
    failed: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def _write_entry(entry: PlanEntry, target_root: str) -> None:
    fsops.clear_target_path(target_root, entry.relpath)
    fsops.copy_file(entry.source, entry.target)
    try:
        fsops.set_mtime_like(entry.target, entry.source)
    except OSError:
        pass


def _delete_entry(entry: PlanEntry, target_root: str) -> None:
    if os.path.isfile(entry.target):
        fsops.remove_file(entry.target)
    # 目标上已经没有这个文件了 —— 可能在消解类型冲突时被一并清掉，视为已完成。


def _sync_kept_mtime(entry: PlanEntry) -> None:
    try:
        if os.stat(entry.target).st_mtime_ns != os.stat(entry.source).st_mtime_ns:
            fsops.set_mtime_like(entry.target, entry.source)
    except OSError:
        pass


def sync_tree(source_root: str, target_root: str, dry_run: bool = False) -> SyncResult:
    """把 ``source_root`` 镜像同步到 ``target_root``。"""
    source_root = os.path.abspath(source_root)
    target_root = os.path.abspath(target_root)

    if not dry_run:
        os.makedirs(target_root, exist_ok=True)

    result = SyncResult()
    bucket = {CREATE: result.created, UPDATE: result.updated, DELETE: result.deleted}
    executor = {CREATE: _write_entry, UPDATE: _write_entry, DELETE: _delete_entry}

    for entry in build_plan(source_root, target_root).entries:
        if entry.action == KEEP:
            result.kept.append(entry.relpath)
            if not dry_run:
                _sync_kept_mtime(entry)
            continue
        if dry_run:
            bucket[entry.action].append(entry.relpath)
            continue
        try:
            executor[entry.action](entry, target_root)
        except OSError as exc:
            result.failed.append(
                {"action": entry.action, "relpath": entry.relpath, "error": str(exc)}
            )
            continue
        bucket[entry.action].append(entry.relpath)

    if not dry_run:
        fsops.prune_empty_dirs(target_root)

    return result
