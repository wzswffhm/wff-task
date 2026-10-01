"""winstall —— Windows 应用的安装 / 升级 / 卸载事务引擎。"""

from __future__ import annotations

from .errors import (
    ApplyFailed,
    NotInstalled,
    PlanRejected,
    WInstallError,
)
from .layout import install_root, payload_dir, product_dir
from .manifest import read_manifest
from .planner import Action, Plan, plan_transaction
from .transaction import ApplyResult, apply_transaction
from .versions import compare_versions, is_upgrade, parse_version

__all__ = [
    "plan_transaction",
    "apply_transaction",
    "Plan",
    "Action",
    "ApplyResult",
    "install_root",
    "product_dir",
    "payload_dir",
    "read_manifest",
    "compare_versions",
    "is_upgrade",
    "parse_version",
    "WInstallError",
    "PlanRejected",
    "ApplyFailed",
    "NotInstalled",
]

__version__ = "2.0.0"
