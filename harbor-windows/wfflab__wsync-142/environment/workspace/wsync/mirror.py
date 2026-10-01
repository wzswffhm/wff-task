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


def _apply(entry: PlanEntry) -> None:
    if entry.action in (CREATE, UPDATE):
        fsops.copy_file(entry.source, entry.target)
    elif entry.action == DELETE:
        fsops.remove_file(entry.target)


def _record(result: SyncResult, action: str, relpath: str) -> None:
    if action == CREATE:
        result.created.append(relpath)
    elif action == UPDATE:
        result.updated.append(relpath)
    elif action == DELETE:
        result.deleted.append(relpath)


def sync_tree(source_root: str, target_root: str, dry_run: bool = False) -> SyncResult:
    """把 ``source_root`` 镜像同步到 ``target_root``。"""
    source_root = os.path.abspath(source_root)
    target_root = os.path.abspath(target_root)

    if not dry_run:
        os.makedirs(target_root, exist_ok=True)

    plan = build_plan(source_root, target_root)
    result = SyncResult()

    for entry in plan.entries:
        if entry.action == KEEP:
            result.kept.append(entry.relpath)
            continue
        if dry_run:
            _record(result, entry.action, entry.relpath)
            continue
        _apply(entry)
        _record(result, entry.action, entry.relpath)

    if not dry_run:
        fsops.prune_empty_dirs(target_root)

    return result
