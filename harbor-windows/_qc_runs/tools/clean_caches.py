# -*- coding: utf-8 -*-
"""清理所有缓存。

删除范围：
  A) 所有 __pycache__ 目录
  B) 批次目录下的 _rejudge 暂存（保留 _qc_runs 下的 backup 存档）
  C) .pytest_cache
  D) .wff-creds/rejudge-stage（判分 stage —— 缓存 bug 根源）
  E) .wff-creds/piptest*（pip 试跑残留）

保留（非缓存）：judge.env / doc-backup / judge-image / 一切 zip / _qc_runs 审计与备份
删除 _rejudge 前先打印其中 reward.json 的值，确认不是未同步的新产物。
"""
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
C = pathlib.Path(r"C:\Users\Administrator\.wff-creds")
freed = 0
removed = []


def dsize(p):
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except Exception:
        return 0


def rm(p: pathlib.Path, kind: str):
    global freed
    if "backup" in str(p).lower():
        print(f"  [SKIP 备份不删] {p}")
        return
    s = dsize(p) if p.is_dir() else p.stat().st_size
    shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    if not p.exists():
        freed += s
        removed.append((kind, str(p), s))
        print(f"  [已删] {s:>10,} B  {p}")


print("=" * 104)
print("安全检查：待删 _rejudge 中的判分产物（确认非本轮未同步产物）")
print("=" * 104)
for p in [ROOT / "harbor-weakness" / "FIN3-WKN-149" / "_rejudge",
          ROOT / "harbor-weakness" / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150" / "_rejudge",
          ROOT / "harbor-weakness" / "work_fin-b01_20261006_fix3-150" / "FIN3-WKN-150" / "_rejudge",
          ROOT / "_qc_runs" / "rejudge151-backup-20261009-100406" / "_rejudge"]:
    if not p.is_dir():
        print(f"  (不存在) {p}")
        continue
    print(f"  {p}")
    for rj in sorted(p.rglob("reward.json")):
        try:
            d = json.loads(rj.read_text(encoding="utf-8"))
            import datetime
            mt = datetime.datetime.fromtimestamp(rj.stat().st_mtime).strftime("%m-%d %H:%M")
            print(f"      {rj.relative_to(p).as_posix():<42} reward={d.get('reward')}  counted={d.get('criteria_counted')}  err={d.get('verifier_error')}  mtime={mt}")
        except Exception as e:
            print(f"      {rj.relative_to(p)}  读取失败 {e}")

print()
print("=" * 104)
print("A) __pycache__")
print("=" * 104)
for p in sorted(ROOT.rglob("__pycache__")) + sorted(C.rglob("__pycache__")):
    if p.is_dir():
        rm(p, "pycache")

print()
print("=" * 104)
print("B) _rejudge 暂存（_qc_runs 下的 backup 会跳过）")
print("=" * 104)
for p in sorted(ROOT.rglob("_rejudge")):
    if p.is_dir():
        rm(p, "_rejudge")

print()
print("=" * 104)
print("C) .pytest_cache")
print("=" * 104)
for p in sorted(ROOT.rglob(".pytest_cache")):
    if p.is_dir():
        rm(p, "pytest_cache")

print()
print("=" * 104)
print("D) .wff-creds/rejudge-stage（缓存 bug 根源，重跑时会按需重建）")
print("=" * 104)
st = C / "rejudge-stage"
if st.is_dir():
    rm(st, "stage")
else:
    print("  (不存在)")

print()
print("=" * 104)
print("E) .wff-creds/piptest*")
print("=" * 104)
for p in [C / "piptest", C / "piptest.err", C / "piptest.out"]:
    if p.exists():
        rm(p, "piptest")
    else:
        print(f"  (不存在) {p}")

print()
print("=" * 104)
print(f"共删除 {len(removed)} 项，回收 {freed:,} B ({freed/1048576:.2f} MB)")
print("=" * 104)
for kind, path, s in removed:
    print(f"  {s:>10,} B  [{kind}]  {path}")

print()
print("=" * 104)
print("保留项核对（非缓存，未删）")
print("=" * 104)
for p in [C / "judge.env", C / "doc-backup", C / "judge-image"]:
    print(f"  {'存在' if p.exists() else '已不存在'}  {p}")
nb = [p for p in ROOT.rglob("*_rejudge*") if "backup" in str(p).lower()]
for p in nb:
    print(f"  保留备份  {p}")
