# -*- coding: utf-8 -*-
"""比较两个目录树的文件哈希差异（相对路径 + sha256）。"""
import hashlib
import pathlib
import sys


def walk(root):
    root = pathlib.Path(root)
    out = {}
    for p in root.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


a_root, b_root = sys.argv[1], sys.argv[2]
a, b = walk(a_root), walk(b_root)
only_a = sorted(set(a) - set(b))
only_b = sorted(set(b) - set(a))
diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
print(f"A={a_root}  files={len(a)}")
print(f"B={b_root}  files={len(b)}")
print(f"-- 仅 A({len(only_a)}) --")
for k in only_a[:40]:
    print("  ", k)
print(f"-- 仅 B({len(only_b)}) --")
for k in only_b[:40]:
    print("  ", k)
print(f"-- 内容不同({len(diff)}) --")
for k in diff[:60]:
    print("  ", k)
