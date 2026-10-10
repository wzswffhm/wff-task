# -*- coding: utf-8 -*-
"""盘点 152 相关的旧跑分产物（v1/v2/v3），标注删除/保留。
只读，不删除。"""
import datetime
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
Q = H / "_qc_runs"
BATCH = H / "work_fin-b01_20261009-152"


def dsize(p):
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0


def trial_summary(d):
    """读 d/trials 下各 trial 的 reward。"""
    out = []
    t = d / "trials"
    if not t.is_dir():
        return out
    for tr in sorted(t.iterdir()):
        if not tr.is_dir():
            continue
        rj = tr / "verifier" / "reward.json"
        if rj.exists():
            try:
                j = json.loads(rj.read_text(encoding="utf-8"))
                out.append(f"{tr.name}: reward={j.get('reward')} err={j.get('verifier_error')}")
            except Exception:
                out.append(f"{tr.name}: (读取失败)")
        else:
            out.append(f"{tr.name}: (无 reward)")
    return out


print("=" * 104)
print("A) _qc_runs 下 152 相关跑分目录")
print("=" * 104)
old_dirs, new_dirs, other = [], [], []
for p in sorted(Q.iterdir()):
    if not p.is_dir():
        continue
    n = p.name
    if "152" not in n:
        continue
    # v4 或与 v4 同名的保留
    if "v4" in n:
        new_dirs.append(p)
        tag = "保留(v4)"
    elif "152" in n:
        old_dirs.append(p)
        tag = "删除(旧)"
    else:
        other.append(p)
        tag = "?"
    s = dsize(p)
    mt = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
    print(f"  [{tag}] {n:<26} {s:>12,} B  {mt}  {sum(1 for _ in p.rglob('*') if _.is_file()):>4} 文件")
    for line in trial_summary(p):
        print(f"            {line}")

print()
print("=" * 104)
print("B) _backup 下 152 相关（区分跑分产物 vs 金标/题包备份）")
print("=" * 104)
BK = H / "_backup"
if BK.is_dir():
    for p in sorted(BK.iterdir()):
        if "152" not in p.name:
            continue
        s = dsize(p)
        kind = "跑分产物" if ("跑分" in p.name or "v1" in p.name and "work_fin" in p.name) else "其他"
        # 更精确：看是否含 跑分产物与轨迹
        has_runs = any("跑分产物" in str(x) for x in p.rglob("*"))
        print(f"  {p.name:<44} {s:>12,} B  含跑分产物={has_runs}")

print()
print("=" * 104)
print("C) 批次目录内旧 跑分产物与轨迹")
print("=" * 104)
for cand in [BATCH / "跑分产物与轨迹",
             BATCH / "FIN3-WKN-152" / "跑分产物与轨迹"]:
    if cand.exists():
        files = [f for f in cand.rglob("*") if f.is_file()]
        print(f"  {cand}")
        print(f"      {len(files)} 文件  {dsize(cand):,} B")
        for f in files[:8]:
            print(f"      - {f.relative_to(cand).as_posix()} ({f.stat().st_size:,} B)")
        if len(files) > 8:
            print(f"      - … 另 {len(files)-8} 个")

print()
print("=" * 104)
print("D) 非 152 的题（149/150/151）跑分产物 —— 本次不碰")
print("=" * 104)
keep = []
for p in sorted(Q.iterdir()):
    if p.is_dir() and any(k in p.name for k in ("149", "150", "151")):
        keep.append(f"{p.name} ({dsize(p):,} B)")
for k in keep:
    print(f"  [保留] {k}")
if not keep:
    print("  （_qc_runs 下无 149/150/151 目录）")

print()
print("=" * 104)
print("汇总：拟删除")
print("=" * 104)
tot = 0
for p in old_dirs:
    s = dsize(p)
    tot += s
    print(f"  - {p}  {s:,} B")
print(f"  小计 {len(old_dirs)} 个目录, {tot:,} B ({tot/1048576:.2f} MB)")
print(f"  另有批次内旧归档与 _backup 中的 v1 跑分归档（见 B/C）")
