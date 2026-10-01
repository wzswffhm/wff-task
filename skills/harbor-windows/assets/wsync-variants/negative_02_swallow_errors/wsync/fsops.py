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
    "make_writable",
    "same_content",
    "set_mtime_like",
    "remove_file",
    "remove_tree",
    "clear_target_path",
    "copy_file",
    "prune_empty_dirs",
]

_CHUNK = 1024 * 1024


def join(root: str, relpath: str) -> str:
    """把目标根目录和一个相对路径拼成绝对路径。"""
    return os.path.join(root, relpath)


def path_key(relpath: str) -> str:
    """把相对路径规整成用于比较的键。

    目标平台的文件系统如何认定“两个路径写的是同一个东西”，由本函数
    决定；调用方不应自己再做字符串拼比较。
    """
    return os.path.normcase(relpath.replace("/", os.sep))


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


def make_writable(path: str) -> None:
    """去掉只读属性，使后续的删除或覆盖可以完成。"""
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IWRITE)


def same_content(left: str, right: str) -> bool:
    """逐块比较两个文件的内容是否完全一致。

    大小与修改时间都相同的两个文件也可能是不同内容（就地改写并保留
    时间戳的工具很常见），所以一致性判定必须落到字节上。
    """
    try:
        if os.path.getsize(left) != os.path.getsize(right):
            return False
        with open(left, "rb") as left_handle, open(right, "rb") as right_handle:
            while True:
                left_chunk = left_handle.read(_CHUNK)
                right_chunk = right_handle.read(_CHUNK)
                if left_chunk != right_chunk:
                    return False
                if not left_chunk:
                    return True
    except OSError:
        return False


def set_mtime_like(target: str, source: str) -> None:
    """把 ``target`` 的访问时间和修改时间对齐到 ``source``。

    备份语义要求目标保留源的时间戳；否则每次同步都会因为“目标看起来
    更新”而产生无谓动作。
    """
    info = os.stat(source)
    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))


def remove_file(path: str) -> None:
    """删除单个文件。

    只读属性会挡住删除，这种情况下先清掉属性再重试；真正的占用
    （共享冲突）不是只读，继续向上抛出交由调用方记录。
    """
    try:
        os.remove(path)
    except PermissionError:
        if not is_readonly(path):
            raise
        make_writable(path)
        os.remove(path)


def remove_tree(path: str) -> None:
    """递归删除一棵目录树，遇到只读条目先清掉属性。"""

    def _retry(func, failed_path, _exc_info):
        if is_readonly(failed_path):
            make_writable(failed_path)
            func(failed_path)
        else:
            raise

    shutil.rmtree(path, onerror=_retry)


def clear_target_path(target_root: str, relpath: str) -> None:
    """清掉目标侧挡在 ``relpath`` 位置上的类型冲突。

    目标平台要求同一条路径不能既是文件又是目录，而路径比较不区分大小写，
    因此：“祖先分量被一个同名文件占住”时要先删掉文件，“路径本身被一个
    同名目录占住”时要先删掉整棵目录。
    """
    parts = [part for part in relpath.replace("/", os.sep).split(os.sep) if part]
    current = target_root
    for part in parts[:-1]:
        current = os.path.join(current, part)
        if os.path.exists(current) and not os.path.isdir(current):
            remove_file(current)
    full = os.path.join(target_root, relpath)
    if os.path.isdir(full):
        remove_tree(full)


def copy_file(source: str, target: str) -> None:
    """把 ``source`` 的内容写到 ``target``，必要时创建父目录。"""
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(target) and is_readonly(target):
        make_writable(target)
    with open(source, "rb") as src_handle, open(target, "wb") as dst_handle:
        shutil.copyfileobj(src_handle, dst_handle, length=_CHUNK)


def prune_empty_dirs(root: str) -> None:
    """自底向上删除目标树中的空目录（不含 ``root`` 自身）。

    目录自身的只读属性会挡住 ``rmdir``，这种情况下先清掉属性再试。
    """
    root = os.path.abspath(root)
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == root:
            continue
        try:
            if os.listdir(dirpath):
                continue
            os.rmdir(dirpath)
        except PermissionError:
            try:
                if not is_readonly(dirpath):
                    continue
                make_writable(dirpath)
                os.rmdir(dirpath)
            except OSError:
                pass
        except OSError:
            pass
