"""把源树与目标树的差异计算成一份可执行的同步计划（**等价对照实现**）。

与参考解的差别：
  - 用 ``filecmp.cmp(shallow=False)`` 判定内容，而不是自己逐块比较
  - 先按路径键建索引再求差集，而不是在循环里逐个 ``in`` 判断
"""

from __future__ import annotations

import filecmp
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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
    if fsops.stat_signature(source_path) is None:
        return False
    try:
        if not os.path.isfile(target_path):
            return True
        return not filecmp.cmp(source_path, target_path, shallow=False)
    except OSError:
        return True


def build_plan(source_root: str, target_root: str) -> Plan:
    source_files = fsops.list_entries(source_root)
    target_files = fsops.list_entries(target_root)

    by_key: Dict[str, Dict[str, str]] = {"s": {}, "t": {}}
    for prefix, table in (("s", source_files), ("t", target_files)):
        for relpath, full in table.items():
            by_key[prefix][fsops.path_key(relpath)] = relpath

    src_keys = set(by_key["s"])
    tgt_keys = set(by_key["t"])

    entries: List[PlanEntry] = []

    for key in sorted(src_keys | tgt_keys):
        in_source = key in src_keys
        in_target = key in tgt_keys
        src_rel = by_key["s"].get(key)
        tgt_rel = by_key["t"].get(key)

        if in_source and in_target:
            source_path = source_files[src_rel]
            target_path = target_files[tgt_rel]
            action = UPDATE if needs_update(source_path, target_path) else KEEP
            entries.append(PlanEntry(action, src_rel, source_path, target_path))
        elif in_source:
            entries.append(
                PlanEntry(CREATE, src_rel, source_files[src_rel],
                          fsops.join(target_root, src_rel))
            )
        else:
            entries.append(PlanEntry(DELETE, tgt_rel, None, target_files[tgt_rel]))

    return Plan(entries)
