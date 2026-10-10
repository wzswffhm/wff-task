# -*- coding: utf-8 -*-
"""移除 152 的所有旧跑分产物（v1/v2/v3）。

删除：
  1) _qc_runs 下 g4-152* 与 g5-152* 的旧 trial 目录（v1/v2/v3，判据已重构，按
     evidence-checks §1.5 这些判分不可再作为难度证据）；
  2) 批次根残留的旧 跑分产物与轨迹（v1 时代 2 个 trial.log，结构不合规）；
  3) _backup 中的 v1 批次归档（含跑分产物）。

保留：
  - 金标备份（FIN3-WKN-152-golden-old-20261010、FIN3-WKN-152-v1）
  - 判据备份（FIN3-WKN-152-rubrics-v3-20261010）
  - 任何 *v4* 目录（v4 跑分将要产生）
  - 149 / 150 / 151 的全部跑分与备份（非本题）
"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
Q = H / "_qc_runs"
BATCH = H / "work_fin-b01_20261009-152"
BK = H / "_backup"

DRY = "--dry-run" in sys.argv


def dsize(p):
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0


def safe(p: pathlib.Path) -> bool:
    """路径必须含 152、不得含 v4、必须在预期根下。"""
    s = str(p)
    return ("152" in s and "v4" not in s
            and (Q in p.parents or BATCH in p.parents or BK in p.parents)
            and p != H)


def rm(p: pathlib.Path, label: str):
    if not p.exists():
        print(f"  [--] 不存在: {p.name}")
        return 0
    assert safe(p), f"路径安全断言失败，拒绝删除: {p}"
    s = dsize(p)
    if DRY:
        print(f"  [dry] {label}: {p.name}  {s:,} B")
        return s
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)
    else:
        p.unlink(missing_ok=True)
    print(f"  [已删] {label}: {p}  {s:,} B")
    return s


print("=" * 98)
print("1) _qc_runs 下 152 的 v1/v2/v3 trial 目录")
print("=" * 98)
t1 = 0
t1n = 0
for p in sorted(Q.iterdir()):
    if not p.is_dir() or "152" not in p.name or "v4" in p.name:
        continue
    t1 += rm(p, "trial")
    t1n += 1
print(f"  小计 {t1n} 个, {t1:,} B ({t1/1048576:.2f} MB)")

print()
print("=" * 98)
print("2) 批次根残留的旧 跑分产物与轨迹（将由 v4 归档重建到题目目录内）")
print("=" * 98)
t2 = rm(BATCH / "跑分产物与轨迹", "批次旧归档")

print()
print("=" * 98)
print("3) _backup 中的 v1 批次归档（含跑分产物）")
print("=" * 98)
t3 = rm(BK / "work_fin-b01_20261009-152-v1", "v1 批次归档备份")

print()
print("=" * 98)
print("保留项复核（必须仍在）")
print("=" * 98)
KEEP = [
    BK / "FIN3-WKN-152-golden-old-20261010",
    BK / "FIN3-WKN-152-rubrics-v3-20261010",
    BK / "FIN3-WKN-152-v1",
    Q / "rejudge150-final-20261009-170123",
]
for p in KEEP:
    print(f"  {'[OK] 存在' if p.exists() else '[!!] 丢失'}  {p.name}")
keep_runs = sorted(p.name for p in Q.iterdir() if p.is_dir() and any(k in p.name for k in ("149", "150", "151")))
print(f"  149/150/151 相关目录仍在: {len(keep_runs)} 个 -> {keep_runs}")
v4 = sorted(p.name for p in Q.iterdir() if p.is_dir() and "152" in p.name and "v4" in p.name)
print(f"  152 v4 目录（尚未产生，跑分后出现）: {v4 if v4 else '无（预期）'}")

print()
print("=" * 98)
print(f"{'[dry-run] 未执行删除' if DRY else '完成'}：合计回收 {t1+t2+t3:,} B ({(t1+t2+t3)/1048576:.2f} MB)")
print("=" * 98)

if not DRY:
    left = sorted(p.name for p in Q.iterdir() if p.is_dir() and "152" in p.name)
    print(f"\n_qc_runs 中剩余含 152 的目录: {left if left else '无（干净）'}")
    print(f"批次根内容: {sorted(p.name for p in BATCH.iterdir()) if BATCH.exists() else '(不存在)'}")
