"""把源树与目标树的差异计算成一份可执行的同步计划。"""

from __future__ import annotations

import os
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
    """目标文件是否需要被源文件覆盖。

    先用大小做廉价筛查，大小相同再逐块比较内容：只凭大小与修改时间无法
    发现“内容被就地改写、时间戳却没变”的文件。
    """
    signature = fsops.stat_signature(source_path)
    if signature is None:
        return False
    if not os.path.isfile(target_path):
        return True
    target_signature = fsops.stat_signature(target_path)
    if target_signature is None or signature[0] != target_signature[0]:
        return True
    return not fsops.same_content(source_path, target_path)


def build_plan(source_root: str, target_root: str) -> Plan:
    """计算从 ``source_root`` 到 ``target_root`` 的镜像同步计划。

    两侧的相对路径先经过 :func:`fsops.path_key` 归一，因此“只有大小写
    不同”的路径会被认定为同一个文件。
    """
    source_files = fsops.list_entries(source_root)
    target_files = fsops.list_entries(target_root)

    target_by_key = {fsops.path_key(rel): rel for rel in target_files}
    source_by_key = {fsops.path_key(rel): rel for rel in source_files}

    entries: List[PlanEntry] = []

    for relpath in sorted(source_files):
        key = fsops.path_key(relpath)
        if key not in target_by_key:
            entries.append(
                PlanEntry(
                    CREATE,
                    relpath,
                    source_files[relpath],
                    fsops.join(target_root, relpath),
                )
            )
            continue
        target_relpath = target_by_key[key]
        if needs_update(source_files[relpath], target_files[target_relpath]):
            entries.append(
                PlanEntry(UPDATE, relpath, source_files[relpath], target_files[target_relpath])
            )
        else:
            entries.append(
                PlanEntry(KEEP, relpath, source_files[relpath], target_files[target_relpath])
            )

    for relpath in sorted(target_files):
        if fsops.path_key(relpath) not in source_by_key:
            entries.append(PlanEntry(DELETE, relpath, None, target_files[relpath]))

    return Plan(entries)
