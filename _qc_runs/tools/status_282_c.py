# -*- coding: utf-8 -*-
"""体检第3步：批次跑分产物详情 + zip 内容 + __golden_output__ 归属判定。"""
import json
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
BATCH = W / "harbor-weakness" / "work_fin-b01_20261009-152"
TASK = W / "harbor-weakness" / "FIN3-WKN-152"
Q = W / "harbor-weakness" / "_qc_runs"

print("=" * 100)
print("1) 批次内 跑分产物与轨迹 详情")
print("=" * 100)
arch = BATCH / "跑分产物与轨迹"
if arch.exists():
    for f in sorted(arch.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(arch).as_posix():<60} {f.stat().st_size:,} B")
            if f.name == "summary.json":
                j = json.loads(f.read_text(encoding="utf-8"))
                print("     " + json.dumps(j, ensure_ascii=False, indent=2)[:2000])

print()
print("=" * 100)
print("2) work_fin-b01_20261009-152.zip 内容结构")
print("=" * 100)
zp = Q / "packages" / "work_fin-b01_20261006-152.zip"
for cand in [Q / "packages" / "work_fin-b01_20261009-152.zip"]:
    if cand.exists():
        with zipfile.ZipFile(cand) as z:
            names = z.namelist()
            tops = sorted({n.split("/")[0] for n in names})
            seconds = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
            print(f"  {cand.name}  {cand.stat().st_size:,} B  entries={len(names)}")
            print(f"  顶层: {tops}")
            print(f"  第二层: {seconds}")
            print("  含 __golden_output__ 的条目:",
                  [n for n in names if "__golden_output__" in n][:10] or "无")
            print("  含 _rejudge/__pycache__:",
                  [n for n in names if "_rejudge" in n or "__pycache__" in n][:5] or "无")
            # 跑分产物
            runs = [n for n in names if "跑分产物与轨迹" in n]
            print(f"  跑分产物条目 {len(runs)} 个:")
            for n in sorted(runs)[:40]:
                print(f"      {n}")

print()
print("=" * 100)
print("3) __golden_output__ 归属：谁新谁旧 + 是否等于 solution 侧")
print("=" * 100)
import hashlib
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
dirs = {
    "tests/__golden_output": TASK / "tests" / "__golden_output",
    "tests/__golden_output__": TASK / "tests" / "__golden_output__",
    "solution/golden_output": TASK / "solution" / "golden_output",
}
import datetime
for label, d in dirs.items():
    if d.exists():
        print(f"  {label}:")
        for f in sorted(d.iterdir()):
            if f.is_file():
                mt = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
                print(f"      {f.name:<45} {f.stat().st_size:>9,} B  {sha(f)}  {mt}")

print()
print("=" * 100)
print("4) 交付文档.md 头 60 行（批次现状）")
print("=" * 100)
doc = BATCH / "交付文档.md"
if doc.exists():
    lines = doc.read_text(encoding="utf-8").splitlines()
    for i, l in enumerate(lines[:60], 1):
        print(f"  {i:>3}: {l[:160]}")
