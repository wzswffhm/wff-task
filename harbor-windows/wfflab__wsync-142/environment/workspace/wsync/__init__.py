"""wsync —— 企业 Windows 环境下的确定性目录镜像同步。

公共入口::

    from wsync import build_plan, sync_tree

    plan = build_plan(source_root, target_root)
    result = sync_tree(source_root, target_root)
    if not result.ok:
        for item in result.failed:
            print(item["action"], item["relpath"], item["error"])
"""

from .errors import SourceTargetCollisionError, SyncError, TargetInUseError
from .mirror import SyncResult, sync_tree
from .planner import CREATE, DELETE, KEEP, UPDATE, Plan, PlanEntry, build_plan

__version__ = "0.4.2"

__all__ = [
    "SyncError",
    "TargetInUseError",
    "SourceTargetCollisionError",
    "SyncResult",
    "sync_tree",
    "build_plan",
    "Plan",
    "PlanEntry",
    "CREATE",
    "UPDATE",
    "DELETE",
    "KEEP",
]
