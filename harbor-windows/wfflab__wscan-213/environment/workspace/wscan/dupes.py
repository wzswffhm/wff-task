"""内容级去重：把重复文件替换为硬链接。"""

import hashlib
import os

_CHUNK = 1 << 20


def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def dedupe(root):
    """把内容相同的重复文件替换为指向规范的硬链接。

    返回被转换为硬链接的相对路径（已排序）。
    """
    groups = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            groups.setdefault(_digest(path), []).append(rel)
    linked = []
    for paths in groups.values():
        if len(paths) < 2:
            continue
        paths.sort()
        canonical = os.path.join(root, paths[0])
        for rel in paths[1:]:
            os.link(canonical, os.path.join(root, rel))
            linked.append(rel)
    return sorted(linked)
