"""把源树与目标树的差异计算成一份可执行的同步计划。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import fsops

CREATE = "create"
UPDATE = "update"
DELETE = "delete"
KEEP = "keep"


@dataclass
class PlanEntry:
    """计划中的一条动作。"""

    action: str
    relpath: str
    source: Optional[str] = None
    target: Optional[str] = None


@dataclass
class Plan:
    """一次同步的完整计划。"""

    entries: List[PlanEntry] = field(default_factory=list)

    def actions(self) -> List[str]:
        return [entry.action for entry in self.entries]

    def by_action(self, action: str) -> List[PlanEntry]:
        return [entry for entry in self.entries if entry.action == action]


def needs_update(source_path: str, target_path: str) -> bool:
    """目标文件是否需要被源文件覆盖。"""
    signature = fsops.stat_signature(source_path)
    if signature is None:
        return False
    return signature != fsops.stat_signature(target_path)


def build_plan(source_root: str, target_root: str) -> Plan:
    """计算从 ``source_root`` 到 ``target_root`` 的镜像同步计划。"""
    source_files = fsops.list_entries(source_root)
    target_files = fsops.list_entries(target_root)

    entries: List[PlanEntry] = []

    for relpath in sorted(source_files):
        if relpath not in target_files:
            entries.append(
                PlanEntry(
                    CREATE,
                    relpath,
                    source_files[relpath],
                    fsops.join(target_root, relpath),
                )
            )
        elif needs_update(source_files[relpath], target_files[relpath]):
            entries.append(
                PlanEntry(UPDATE, relpath, source_files[relpath], target_files[relpath])
            )
        else:
            entries.append(
                PlanEntry(KEEP, relpath, source_files[relpath], target_files[relpath])
            )

    for relpath in sorted(target_files):
        if relpath not in source_files:
            entries.append(PlanEntry(DELETE, relpath, None, target_files[relpath]))

    return Plan(entries)
