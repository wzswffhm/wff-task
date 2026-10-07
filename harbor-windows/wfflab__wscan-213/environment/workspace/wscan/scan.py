"""目录扫描与统计。"""

import os


class ScanResult:
    """scan_tree 的返回值。

    files            相对 root 的文件路径列表（os.path.join 风格，已排序）
    total_bytes      全部普通文件的 st_size 之和
    hard_link_groups 硬链接簇列表：每簇是身份相同（>=2 个路径）的
                     相对路径列表；簇内与簇间均已排序
    """

    def __init__(self, files, total_bytes, hard_link_groups):
        self.files = files
        self.total_bytes = total_bytes
        self.hard_link_groups = hard_link_groups

    def __repr__(self):
        return "ScanResult(files=%d, total_bytes=%d, hard_link_groups=%d)" % (
            len(self.files), self.total_bytes, len(self.hard_link_groups))


def scan_tree(root):
    """扫描 ``root`` 目录树，统计文件、总字节与硬链接簇。"""
    files = []
    by_signature = {}
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            st = os.stat(path)
            files.append(rel)
            total += st.st_size
            by_signature.setdefault((st.st_size, st.st_mtime_ns), []).append(rel)
    files.sort()
    groups = [sorted(paths) for paths in by_signature.values() if len(paths) > 1]
    groups.sort()
    return ScanResult(files=files, total_bytes=total, hard_link_groups=groups)
