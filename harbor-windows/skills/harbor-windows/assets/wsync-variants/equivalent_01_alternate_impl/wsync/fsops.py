"""wsync 的底层文件系统操作（**等价对照实现**）。

与参考解在结构上刻意不同，用来证明隐藏测试验收的是**行为**而不是某一种写法：
  - 目录遍历用 ``os.scandir`` 递归，不用 ``os.walk``
  - 内容比对用 sha256 摘要，不做逐块比较
  - 落盘走「写临时文件 + os.replace 原子替换」
  - 时间戳在替换之前就挂到临时文件上，不是复制完再补
  - 只读障碍统一走 ``_retry_writable`` 的执行器重试
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from typing import Dict, Optional, Tuple

__all__ = [
    "join",
    "path_key",
    "list_entries",
    "stat_signature",
    "is_readonly",
    "make_writable",
    "same_content",
    "set_mtime_like",
    "remove_file",
    "remove_tree",
    "clear_target_path",
    "copy_file",
    "prune_empty_dirs",
]

_BLOCK = 512 * 1024


def join(root: str, relpath: str) -> str:
    return os.path.join(root, relpath)


def path_key(relpath: str) -> str:
    """目标平台的路径比较键：统一分隔符并折叠大小写。"""
    return relpath.replace("/", os.sep).lower()


def list_entries(root: str) -> Dict[str, str]:
    found: Dict[str, str] = {}
    if not os.path.isdir(root):
        return found
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for item in it:
                    try:
                        if item.is_dir():
                            stack.append(item.path)
                        elif item.is_file():
                            found[os.path.relpath(item.path, root)] = item.path
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def stat_signature(path: str) -> Optional[Tuple[int, int]]:
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_size, info.st_mtime_ns)


def is_readonly(path: str) -> bool:
    try:
        return not (os.stat(path).st_mode & stat.S_IWRITE)
    except OSError:
        return False


def make_writable(path: str) -> None:
    info = os.stat(path)
    os.chmod(path, info.st_mode | stat.S_IWRITE)


def _digest(path: str) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                block = fh.read(_BLOCK)
                if not block:
                    break
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def same_content(left: str, right: str) -> bool:
    try:
        if os.path.getsize(left) != os.path.getsize(right):
            return False
    except OSError:
        return False
    left_digest = _digest(left)
    return left_digest is not None and left_digest == _digest(right)


def set_mtime_like(target: str, source: str) -> None:
    info = os.stat(source)
    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))


def _retry_writable(operation, path: str) -> None:
    """执行操作；遇到只读属性造成的拒绝访问就清属性重试，其它 PermissionError 照抛。"""
    try:
        operation(path)
    except PermissionError:
        if not is_readonly(path):
            raise
        make_writable(path)
        operation(path)


def remove_file(path: str) -> None:
    _retry_writable(os.remove, path)


def remove_tree(path: str) -> None:
    def _handle(func, failed_path, _exc_info):
        if is_readonly(failed_path):
            make_writable(failed_path)
            func(failed_path)
        else:
            raise

    shutil.rmtree(path, onerror=_handle)


def clear_target_path(target_root: str, relpath: str) -> None:
    segments = [s for s in relpath.replace("/", os.sep).split(os.sep) if s]
    node = target_root
    for segment in segments[:-1]:
        node = os.path.join(node, segment)
        if os.path.isfile(node):
            remove_file(node)
    leaf = os.path.join(target_root, relpath)
    if os.path.isdir(leaf):
        remove_tree(leaf)


def copy_file(source: str, target: str) -> None:
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    staging = target + ".wsync-part"
    if os.path.exists(staging):
        remove_file(staging)
    with open(source, "rb") as src_handle, open(staging, "wb") as dst_handle:
        shutil.copyfileobj(src_handle, dst_handle, length=_BLOCK)
    # 先把时间戳挂到临时文件上，再做原子替换：目标一出现就已经是对齐的。
    set_mtime_like(staging, source)
    if os.path.exists(target) and is_readonly(target):
        make_writable(target)
    os.replace(staging, target)


def prune_empty_dirs(root: str) -> None:
    root = os.path.abspath(root)
    stack = [root]
    visited = []
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                children = [c.path for c in it if c.is_dir()]
        except OSError:
            continue
        visited.append(current)
        stack.extend(children)
    for directory in reversed(visited):
        if os.path.abspath(directory) == root:
            continue
        try:
            if os.listdir(directory):
                continue
            _retry_writable(os.rmdir, directory)
        except OSError:
            pass
