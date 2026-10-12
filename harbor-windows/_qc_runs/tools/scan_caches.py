# -*- coding: utf-8 -*-
"""盘点所有缓存候选（只读，不删除）。

分类：
  A 目录级缓存：__pycache__ / _rejudge（判分暂存）
  B 文件级缓存：*.pyc / *.pyo
  C 暂存工作区：.wff-creds 下的 stage 类目录（逐项列出内容以便判断）
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOTS = [
    pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task"),
    pathlib.Path(r"C:\Users\Administrator\.wff-creds"),
]


def dsize(p: pathlib.Path) -> int:
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0


print("=" * 104)
print("A) __pycache__ 目录")
print("=" * 104)
a_total = 0
a_count = 0
for root in ROOTS:
    if not root.is_dir():
        continue
    for p in sorted(root.rglob("__pycache__")):
        if p.is_dir():
            s = dsize(p)
            a_total += s
            a_count += 1
            print(f"  {s:>10,} B  {p}")
print(f"  小计: {a_count} 个目录, {a_total:,} B")

print()
print("=" * 104)
print("B) _rejudge 目录（判分暂存）")
print("=" * 104)
b_total = 0
b_count = 0
for root in ROOTS:
    if not root.is_dir():
        continue
    for p in sorted(root.rglob("_rejudge")):
        if p.is_dir():
            s = dsize(p)
            b_total += s
            b_count += 1
            nf = sum(1 for f in p.rglob("*") if f.is_file())
            print(f"  {s:>10,} B  {nf:>4} 文件  {p}")
print(f"  小计: {b_count} 个目录, {b_total:,} B")

print()
print("=" * 104)
print("C) 独立 .pyc / .pyo 文件（不在 __pycache__ 内的）")
print("=" * 104)
c_total = 0
c_count = 0
for root in ROOTS:
    if not root.is_dir():
        continue
    for p in sorted(root.rglob("*.py[co]")):
        if p.is_file() and "__pycache__" not in p.parts:
            c_total += p.stat().st_size
            c_count += 1
            print(f"  {p.stat().st_size:>10,} B  {p}")
print(f"  小计: {c_count} 个文件, {c_total:,} B")

print()
print("=" * 104)
print("D) .wff-creds 下的暂存/工作区目录（逐项列出内容判定用途）")
print("=" * 104)
C = pathlib.Path(r"C:\Users\Administrator\.wff-creds")
if C.is_dir():
    for p in sorted(C.iterdir()):
        if p.is_dir():
            s = dsize(p)
            files = sorted(f for f in p.rglob("*") if f.is_file())
            print(f"  {s:>12,} B  {len(files):>5} 文件  {p.name}/")
            for f in files[:6]:
                print(f"                  └─ {f.relative_to(p)}  ({f.stat().st_size:,} B)")
            if len(files) > 6:
                print(f"                  └─ … 另 {len(files)-6} 个文件")
        else:
            print(f"  {p.stat().st_size:>12,} B  (文件)      {p.name}")

print()
print("=" * 104)
print("E) 其他常见缓存/临时目录")
print("=" * 104)
PATTERNS = [".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints",
            "node_modules", "__snapshots__", ".cache"]
found = False
for root in ROOTS:
    if not root.is_dir():
        continue
    for pat in PATTERNS:
        for p in sorted(root.rglob(pat)):
            if p.is_dir():
                found = True
                print(f"  {dsize(p):>12,} B  {p}")
if not found:
    print("  （无）")

print()
print("=" * 104)
print(f"合计可回收（A+B+C）: {a_total + b_total + c_total:,} B")
print("=" * 104)
