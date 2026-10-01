"""把「想做什么」翻译成一组可以顺序执行的动作。

规划阶段**只读**：不允许创建目录、写文件或改清单。调用方可以先用
:func:`plan_transaction` 拿到计划并检查，再决定是否 :func:`transaction.apply_transaction`。
"""

import os
from collections import namedtuple

from . import layout, manifest
from .errors import PlanRejected
from .versions import is_upgrade, normalize

Action = namedtuple("Action", "kind relpath source")
Plan = namedtuple("Plan", "operation product version scope root actions files previous")

INSTALL = "install"
UNINSTALL = "uninstall"
_OPERATIONS = (INSTALL, UNINSTALL)


def _check_name(value, what):
    text = str(value or "").strip()
    if not text:
        raise ValueError("%s must not be empty" % what)
    if any(ch in text for ch in '\\/:*?"<>|'):
        raise ValueError("%s must not contain path separators: %r" % (what, value))
    return text


def _check_relpath(rel):
    key = layout.relative_key(rel)
    if not key or key.startswith("../") or "/../" in key:
        raise ValueError("payload path escapes the payload directory: %r" % (rel,))
    return key


def plan_transaction(operation, product, version=None, files=None, scope="machine", root=None):
    """规划一次安装或卸载。

    ``files`` 是 ``{相对路径: 源文件路径}``，只在 ``install`` 时使用。
    """
    if operation not in _OPERATIONS:
        raise ValueError("unknown operation: %r" % (operation,))
    product = _check_name(product, "product")
    root = layout.install_root(scope, base=root)
    data = manifest.read_manifest(root)
    current = manifest.get_product(data, product)

    if operation == UNINSTALL:
        if current is None:
            raise PlanRejected("not-installed", "%s is not installed" % product)
        old_version = current.get("version") or ""
        actions = []
        for rel in sorted(current.get("files") or []):
            actions.append(Action("remove", _check_relpath(rel), None))
        return Plan(UNINSTALL, product, old_version, scope, root,
                    tuple(actions), (), current)

    version = normalize(_check_name(version, "version"))
    if not isinstance(files, dict) or not files:
        raise ValueError("files must be a non-empty mapping of relpath -> source")

    if current is not None:
        installed = current.get("version") or ""
        if not is_upgrade(installed, version):
            raise PlanRejected(
                "downgrade",
                "%s %s is already installed; %s is not newer" % (product, installed, version))

    wanted = {}
    for rel, source in files.items():
        key = _check_relpath(rel)
        if key in wanted:
            raise ValueError("duplicate payload path: %r" % (key,))
        wanted[key] = source
    wanted = dict(sorted(wanted.items()))

    actions = [Action("write", rel, str(src)) for rel, src in wanted.items()]
    keep = set(wanted)
    if current is not None:
        for rel in sorted(current.get("files") or []):
            key = _check_relpath(rel)
            if key not in keep:
                actions.append(Action("remove", key, None))

    return Plan(INSTALL, product, version, scope, root, tuple(actions),
                tuple(wanted), current)


def destination(plan, action):
    """某个动作对应的绝对目标路径。"""
    return os.path.join(layout.payload_dir(plan.root, plan.product), action.relpath)
