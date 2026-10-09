# -*- coding: utf-8 -*-
"""以飞书附件为基准，精确区分 harbor-weakness 的"当前有效"与"历史冗余"，并标注 git 状态。只读。"""
import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
W = REPO / "harbor-weakness"

# 飞书当前附件（2026-10-09 实查）
CURRENT = {
    "work_fin-b01_20261005_fix7-149.zip": ("149", "交付物", 8548088),
    "work_fin-b01_20261006_fix3-150.zip": ("150", "交付物", 14057234),
    "work_fin-b01_20261006-151.zip":      ("151", "交付物", 10235600),
    "FIN3-WKN-149_task.zip":   ("149", "题目附件", 335961),
    "FIN3-WKN-149_answer.zip": ("149", "标准答案", 1011976),
    "FIN3-WKN-150_task.zip":   ("150", "题目附件", 68694),
    "FIN3-WKN-150_answer.zip": ("150", "标准答案", 927362),
    "FIN3-WKN-151_task.zip":   ("151", "题目附件", 56928),
    "FIN3-WKN-151_answer.zip": ("151", "标准答案", 587232),
}


def sh(*a):
    return subprocess.run(a, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked(rel):
    return len([x for x in sh("git", "ls-files", "--", rel).splitlines() if x.strip()])


def ignored(rel):
    return subprocess.run(["git", "check-ignore", "-q", "--", rel], cwd=REPO,
                          capture_output=True).returncode == 0


def size(p):
    return sum(q.stat().st_size for q in p.rglob("*") if q.is_file())


def nfiles(p):
    return sum(1 for q in p.rglob("*") if q.is_file())


print("=" * 106)
print("一、题包本体 FIN3-WKN-*")
print("=" * 106)
for d in sorted(x for x in W.glob("FIN3-WKN-*") if x.is_dir()):
    rel = f"harbor-weakness/{d.name}"
    sub = sorted(x.name for x in d.iterdir() if x.is_dir())
    has_rj = (d / "_rejudge").is_dir()
    print(f"  {d.name:<14} {nfiles(d):>4}文件 {size(d)/1024/1024:>6.1f}MB  子目录={sub}")
    print(f"  {'':14} 含_rejudge={has_rj}  已跟踪={tracked(rel):>4}  被忽略={ignored(rel)}")

print()
print("=" * 106)
print("二、zip 分类（对照飞书）")
print("=" * 106)
cur, his = [], []
for z in sorted(W.glob("*.zip")):
    rel = f"harbor-weakness/{z.name}"
    info = CURRENT.get(z.name)
    rec = (z.name, z.stat().st_size, info, tracked(rel), ignored(rel))
    (cur if info else his).append(rec)

print("  【当前有效 = 飞书正在挂的附件】")
for name, s, info, t, ig in cur:
    task, kind, fsize = info
    print(f"    ✓ {name:<42} {s:>12,} B  飞书={fsize:>12,} B 一致={s==fsize}  {task}/{kind}  跟踪={t}")
print(f"    小计 {sum(x[1] for x in cur)/1024/1024:.1f} MB")
print()
print("  【历史冗余 = 飞书上已不存在】")
for name, s, info, t, ig in his:
    print(f"    - {name:<42} {s:>12,} B  跟踪={t}  忽略={ig}")
print(f"    小计 {sum(x[1] for x in his)/1024/1024:.1f} MB")

print()
print("=" * 106)
print("三、批次目录（对照飞书交付包）")
print("=" * 106)
for d in sorted([x for x in W.iterdir() if x.is_dir() and not x.name.startswith("FIN3-WKN")],
                key=lambda x: x.name):
    rel = f"harbor-weakness/{d.name}"
    tasks = sorted(x.name for x in d.iterdir() if x.name.startswith("FIN3-WKN-")) if d.is_dir() else []
    print(f"  {d.name:<46} {nfiles(d):>4}文件 {size(d)/1024/1024:>6.1f}MB 题={tasks} 跟踪={tracked(rel):>4}")

print()
print("=" * 106)
print("四、其它顶层文件")
print("=" * 106)
for f in sorted(W.iterdir()):
    if f.is_file() and f.suffix != ".zip":
        rel = f"harbor-weakness/{f.name}"
        print(f"  {f.name:<46} {f.stat().st_size:>12,} B 跟踪={tracked(rel)}")
