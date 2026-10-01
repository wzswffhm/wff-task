"""执行计划中的动作，并维护清单。

写入采用「同目录临时文件 + 原子替换」：目标位置要么是旧内容，要么是新内容，
不会出现半个文件。
"""

import os
import shutil
from collections import namedtuple

from . import manifest, planner

ApplyResult = namedtuple("ApplyResult", "operation product version applied deferred")

TMP_SUFFIX = ".winstall-part"


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _put_file(source, destination):
    """把 ``source`` 放到 ``destination``（原子替换）。"""
    temporary = destination + TMP_SUFFIX
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def _delete_file(path):
    if os.path.isfile(path):
        os.remove(path)


def apply_transaction(plan):
    """顺序执行 ``plan`` 中的动作，然后更新清单。"""
    applied = []
    for action in plan.actions:
        target = planner.destination(plan, action)
        if action.kind == "write":
            _ensure_parent(target)
            _put_file(action.source, target)
        elif action.kind == "remove":
            _delete_file(target)
        else:
            raise ValueError("unknown action: %r" % (action.kind,))
        applied.append(action.relpath)

    data = manifest.read_manifest(plan.root)
    if plan.operation == planner.INSTALL:
        manifest.set_product(data, plan.product, plan.version, plan.files, [])
    else:
        manifest.drop_product(data, plan.product)
    manifest.write_manifest(plan.root, data)

    return ApplyResult(plan.operation, plan.product, plan.version,
                       tuple(applied), ())
