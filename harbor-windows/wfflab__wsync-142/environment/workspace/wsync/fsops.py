"""wsync 的底层文件系统操作。

所有直接接触磁盘的调用都集中在本模块，这样文件属性、路径形式和共享
冲突的处理就只有一个地方需要关心。
"""

from __future__ import annotations

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
    "remove_file",
    "remove_tree",
    "copy_file",
    "prune_empty_dirs",
]


def join(root: str, relpath: str) -> str:
    """把目标根目录和一个相对路径拼成绝对路径。"""
    return os.path.join(root, relpath)


def path_key(relpath: str) -> str:
    """把相对路径规整成用于比较的键。

    目标平台的文件系统如何认定“两个路径写的是同一个东西”，由本函数
    决定；调用方不应自己再做字符串拼比较。
    """
    return relpath.replace("/", os.sep)


def list_entries(root: str) -> Dict[str, str]:
    """列出目录树中的所有普通文件。

    返回 ``{相对路径: 绝对路径}``；``root`` 不存在时返回空字典。
    """
    entries: Dict[str, str] = {}
    if not os.path.isdir(root):
        return entries
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            entries[os.path.relpath(full, root)] = full
    return entries


def stat_signature(path: str) -> Optional[Tuple[int, int]]:
    """返回用于“内容是否变化”判定的签名。

    签名由大小与修改时间共同构成；读取失败时返回 ``None``。
    """
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (info.st_size, info.st_mtime_ns)


def is_readonly(path: str) -> bool:
    """路径是否带有只读属性。"""
    try:
        info = os.stat(path)
    except OSError:
        return False
    return not bool(info.st_mode & stat.S_IWRITE)


def remove_file(path: str) -> None:
    """删除单个文件。"""
    os.remove(path)


def remove_tree(path: str) -> None:
    """递归删除一棵目录树。"""
    shutil.rmtree(path)


def copy_file(source: str, target: str) -> None:
    """把 ``source`` 的内容写到 ``target``，必要时创建父目录。"""
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(source, "rb") as src_handle, open(target, "wb") as dst_handle:
        shutil.copyfileobj(src_handle, dst_handle, length=1024 * 1024)


def prune_empty_dirs(root: str) -> None:
    """自底向上删除目标树中的空目录（不含 ``root`` 自身）。"""
    root = os.path.abspath(root)
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == root:
            continue
        try:
            if not os.listdir(dirpath):
                os.rmdir(dirpath)
        except OSError:
            pass
