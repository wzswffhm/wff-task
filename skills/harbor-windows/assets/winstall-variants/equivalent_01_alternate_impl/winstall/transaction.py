"""执行计划中的动作，并维护清单（等价实现：整目录快照回滚）。

与参考解的差别在回滚机制：这里在执行前把整个产品目录复制成快照，
失败时删掉产品目录再从快照还原，而不是逐步记录每个文件的前后状态。
写文件也不用 shutil.copyfile，而是显式字节流。
"""

import os
import shutil
import tempfile
from collections import namedtuple

from . import layout, manifest, planner
from .errors import ApplyFailed

ApplyResult = namedtuple("ApplyResult", "operation product version applied deferred")

TMP_SUFFIX = ".winstall-part"


def _sweep(destination):
    try:
        os.remove(destination + TMP_SUFFIX)
    except OSError:
        pass


def _write_file(source, destination):
    temporary = destination + TMP_SUFFIX
    with open(source, "rb") as src, open(temporary, "wb") as dst:
        while True:
            chunk = src.read(1 << 16)
            if not chunk:
                break
            dst.write(chunk)
    try:
        os.replace(temporary, destination)
    except OSError:
        _sweep(destination)
        raise


def _locked(exc, destination):
    """目标当前是普通文件、且失败原因是共享冲突 / 访问拒绝时，才允许推迟。"""
    if os.path.isdir(destination) or not os.path.isfile(destination):
        return False
    if not isinstance(exc, PermissionError):
        return False
    code = getattr(exc, "winerror", None)
    if code is None:
        return exc.errno in (11, 13)
    return code in (5, 32, 33)


def apply_transaction(plan):
    """顺序执行 ``plan`` 中的动作，然后更新清单。"""
    product_root = layout.product_dir(plan.root, plan.product)
    manifest_file = manifest.manifest_path(plan.root)
    staging = tempfile.mkdtemp(prefix="winstall-snap-")
    snapshot = os.path.join(staging, "snapshot")
    had_product = os.path.isdir(product_root)
    if had_product:
        shutil.copytree(product_root, snapshot)
    had_manifest = os.path.isfile(manifest_file)
    if had_manifest:
        shutil.copyfile(manifest_file, os.path.join(staging, "installed.json.bak"))

    applied = []
    deferred = []
    try:
        for action in plan.actions:
            target = planner.destination(plan, action)
            if action.kind == "write":
                parent = os.path.dirname(target)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                try:
                    _write_file(action.source, target)
                except OSError as exc:
                    if not _locked(exc, target):
                        raise ApplyFailed(action.relpath, str(exc))
                    deferred.append(action.relpath)
                    continue
            elif action.kind == "remove":
                if os.path.isfile(target):
                    os.remove(target)
            else:
                raise ValueError("unknown action: %r" % (action.kind,))
            applied.append(action.relpath)

        data = manifest.read_manifest(plan.root)
        if plan.operation == planner.INSTALL:
            manifest.set_product(data, plan.product, plan.version, plan.files, deferred)
        else:
            manifest.drop_product(data, plan.product)
        manifest.write_manifest(plan.root, data)
    except BaseException:
        shutil.rmtree(product_root, ignore_errors=True)
        if had_product:
            shutil.copytree(snapshot, product_root)
        if had_manifest:
            shutil.copyfile(os.path.join(staging, "installed.json.bak"), manifest_file)
        elif os.path.isfile(manifest_file):
            os.remove(manifest_file)
        shutil.rmtree(staging, ignore_errors=True)
        raise

    shutil.rmtree(staging, ignore_errors=True)
    return ApplyResult(plan.operation, plan.product, plan.version,
                       tuple(applied), tuple(deferred))
