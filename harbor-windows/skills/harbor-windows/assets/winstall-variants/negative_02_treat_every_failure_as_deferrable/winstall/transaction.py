"""执行计划中的动作，并维护清单。

写入采用「同目录临时文件 + 原子替换」：目标位置要么是旧内容，要么是新内容，
不会出现半个文件。

Windows 上如果目标文件正被其它进程打开，原子替换会失败。这类失败是
**可延迟**的：该文件保持旧内容不动、记入 ``deferred``，等下一次执行再替换；
其余动作照常进行。除此之外的任何失败都必须**回滚**——产品载荷、清单
都要回到执行前的状态。
"""

import os
import shutil
import tempfile
from collections import namedtuple

from . import manifest, planner
from .errors import ApplyFailed

ApplyResult = namedtuple("ApplyResult", "operation product version applied deferred")

TMP_SUFFIX = ".winstall-part"

#: 目标文件被占用时 Windows 给出的错误码：
#: 5 = ERROR_ACCESS_DENIED，32 = ERROR_SHARING_VIOLATION，33 = ERROR_LOCK_VIOLATION。
_LOCK_WINERRORS = (5, 32, 33)


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _is_deferrable(exc, destination):
    """这个失败能不能推迟到下一次执行？

    只有「目标当前是一个普通文件、只是被别的进程打开着」才可推迟。
    目标位置被同名目录占据、路径非法、磁盘错误等都必须当成硬失败——
    这些和「被占用」在错误码上可能完全相同，只能看目标本身是什么。
    """
    if not isinstance(exc, PermissionError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror is None:
        return exc.errno in (11, 13)
    return winerror in _LOCK_WINERRORS


def _remove_quietly(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _put_file(source, destination):
    """把 ``source`` 放到 ``destination``（原子替换）。

    临时文件在任何失败路径上都会被清掉，不允许留在载荷目录里。
    """
    temporary = destination + TMP_SUFFIX
    shutil.copyfile(source, temporary)
    try:
        os.replace(temporary, destination)
    except BaseException:
        _remove_quietly(temporary)
        raise


def _backup(destination, staging):
    """把将被覆盖 / 删除的东西备份到事务暂存区，返回备份路径（不存在则 ``None``）。"""
    if os.path.isfile(destination):
        saved = os.path.join(staging, "backup-%04d" % len(os.listdir(staging)))
        shutil.copyfile(destination, saved)
        return saved
    return None


def _restore(undo):
    """逆序回滚：有备份的恢复内容，没有备份的删掉。"""
    for destination, backup in reversed(undo):
        try:
            if backup is None:
                if os.path.isfile(destination):
                    os.remove(destination)
            else:
                shutil.copyfile(backup, destination)
        except OSError:
            pass


def _drop_temporaries(plan):
    for action in plan.actions:
        if action.kind == "write":
            _remove_quietly(planner.destination(plan, action) + TMP_SUFFIX)


def apply_transaction(plan):
    """顺序执行 ``plan`` 中的动作，然后更新清单。

    可延迟的失败只影响单个文件；任何不可延迟的失败都会回滚并抛出
    :class:`ApplyFailed`。
    """
    staging = tempfile.mkdtemp(prefix="winstall-tx-")
    manifest_file = manifest.manifest_path(plan.root)
    undo = [(manifest_file, _backup(manifest_file, staging))]
    applied = []
    deferred = []
    try:
        for action in plan.actions:
            target = planner.destination(plan, action)
            if action.kind == "write":
                _ensure_parent(target)
                undo.append((target, _backup(target, staging)))
                try:
                    _put_file(action.source, target)
                except OSError as exc:
                    if not _is_deferrable(exc, target):
                        raise ApplyFailed(action.relpath, str(exc))
                    # 旧内容保持不动，撤回刚刚做的备份记录
                    undo.pop()
                    deferred.append(action.relpath)
                    continue
            elif action.kind == "remove":
                undo.append((target, _backup(target, staging)))
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
        _restore(undo)
        _drop_temporaries(plan)
        shutil.rmtree(staging, ignore_errors=True)
        raise

    shutil.rmtree(staging, ignore_errors=True)
    return ApplyResult(plan.operation, plan.product, plan.version,
                       tuple(applied), tuple(deferred))
