# -*- coding: utf-8 -*-
"""清理 harbor-weakness 的 A 类冗余：飞书上已不存在的 8 个历史版本 zip。

安全约束：
  - 严格按白名单文件名删除，不做通配；
  - 删除前逐一复核：不在飞书当前附件清单内；
  - 每个文件都被 git 跟踪，删除后可从版本库恢复（git checkout -- <path>）。
"""
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
W = REPO / "harbor-weakness"

# 飞书当前正在挂的附件（必须保留）
KEEP = {
    "work_fin-b01_20261005_fix7-149.zip", "work_fin-b01_20261006_fix3-150.zip",
    "work_fin-b01_20261006-151.zip", "FIN3-WKN-149_task.zip", "FIN3-WKN-149_answer.zip",
    "FIN3-WKN-150_task.zip", "FIN3-WKN-150_answer.zip", "FIN3-WKN-151_task.zip",
    "FIN3-WKN-151_answer.zip",
}

# A 类清理白名单
TARGETS = [
    "work_fin-b01_20261001_fix1.zip",
    "work_fin-b01_20261002_fix2.zip",
    "work_fin-b01_20261002_fix3.zip",
    "work_fin-b01_20261003_fix4.zip",
    "work_fin-b01_20261004_fix5-149.zip",
    "work_fin-b01_20261005-151.zip",
    "work_fin-b01_20261005_fix6-149.zip",
    "work_fin-b01_20261006_fix2-150.zip",
]

DRY = "--dry-run" in sys.argv

print("=" * 92)
print("A 类清理：历史版本 zip（飞书上已不存在）")
print("=" * 92)

total = 0
deleted, skipped = [], []
for name in TARGETS:
    p = W / name
    if not p.is_file():
        print(f"  [跳过] {name}  (不存在)")
        skipped.append(name)
        continue
    if name in KEEP:
        print(f"  [危险] {name} 在飞书当前清单内，拒绝删除")
        skipped.append(name)
        continue
    size = p.stat().st_size
    total += size
    print(f"  删除 {name:<44} {size:>12,} B")
    if not DRY:
        p.unlink()
    deleted.append(name)

print()
print(f"  共删除 {len(deleted)} 个文件，释放 {total:,} B ({total/1024/1024:.1f} MB)")
if skipped:
    print(f"  跳过 {len(skipped)} 个：{skipped}")

# ---- 复核：确认保留项完好 ----
print()
print("=" * 92)
print("复核：飞书当前附件是否都还在")
print("=" * 92)
ok = True
for name in sorted(KEEP):
    p = W / name
    exist = p.is_file()
    if not exist:
        ok = False
    print(f"  {'✓' if exist else '✗ 缺失'} {name:<44} {p.stat().st_size if exist else 0:>12,} B")
print()
print(">>> 全部保留项完好" if ok else ">>> 有保留项缺失，需立即处理")

# ---- 剩余 zip 清单 ----
print()
print("=" * 92)
print("剩余 zip")
print("=" * 92)
rest = sorted(W.glob("*.zip"))
tot = 0
for z in rest:
    tot += z.stat().st_size
    tag = "飞书当前" if z.name in KEEP else "其它"
    print(f"  [{tag}] {z.name:<44} {z.stat().st_size:>12,} B")
print(f"  共 {len(rest)} 个，{tot/1024/1024:.1f} MB")

# ---- git 状态 ----
print()
print("=" * 92)
print("git 状态（harbor-weakness 下的变更）")
print("=" * 92)
r = subprocess.run(["git", "status", "--short", "--", "harbor-weakness"],
                   cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
lines = [x for x in r.stdout.splitlines() if x.strip()]
zip_del = [x for x in lines if x.strip().startswith("D") and ".zip" in x]
print(f"  harbor-weakness 变更总数: {len(lines)}")
print(f"  其中删除的 zip: {len(zip_del)}")
for x in zip_del:
    print(f"    {x}")
