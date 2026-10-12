# -*- coding: utf-8 -*-
"""扫描 152 交付包（题包本体 + 批次 + 三个 zip）的旧数据残留。
v1/v2/v3 痕迹、旧分数、旧判据数/正分池、旧难度、旧批次名、占位符、判据泄漏等。
"""
import json
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = H / "FIN3-WKN-152"
BATCH = H / "work_fin-b01_20261009-152"
PKG = H / "_qc_runs" / "packages"

# ── 旧数据特征（值, 说明）──
OLD = [
    # 旧难度
    ("A3", "旧难度 A3（应为 A2）"),
    # 旧判据数 / 正分池
    ("27 条", "v1 判据数"),
    ("33 条", "v2 判据数（历史对照表除外）"),
    ("37 条", "v3 判据数"),
    ("S_max 153", "v1 正分池"),
    ("S_max 179", "v2 正分池"),
    ("S_max 207", "v3 正分池"),
    ("s_max\": 153", "v1 s_max"),
    ("s_max\": 179", "v2 s_max"),
    ("s_max\": 207", "v3 s_max"),
    # 旧分数
    ("0.932367", "v3 oracle 分"),
    ("0.98324", "v2 分"),
    ("0.9852", "v2 分"),
    ("0.621970", "fix3 均值"),
    ("1.000000", "v1/v3 满分"),
    # 旧版本
    ("1.0.0", "v1 版本"),
    ("2.0.0", "v2 版本"),
    ("3.0.0", "v3 版本"),
    ("v2.0.0", "v2 标题"),
    ("v3.0.0", "v3 描述"),
    # 旧批次名
    ("fix3-150", "150 批次串味"),
    ("FIN3-WKN-150", "150 题串味"),
    ("FIN3-WKN-149", "149 题串味"),
    ("FIN3-WKN-151", "151 题串味"),
    # 旧 trial 名
    ("__Sa7ciyW", "v1 trial"),
    ("__vFbfvgm", "v1 trial"),
    ("oracle-152v2", "v2 trial"),
    ("oracle-152v3", "v3 trial"),
    ("152v2", "v2 trial"),
    ("152v3", "v3 trial"),
    # 占位符
    ("[[G4_REWARD]]", "未回填"),
    ("[[G5_MEAN]]", "未回填"),
    ("[[DIFFICULTY]]", "未回填"),
    ("[[G4_SECTION]]", "未回填"),
    ("[[G5_SECTION]]", "未回填"),
    # 判据泄漏/引导
    ("锚点收紧", "150 式描述"),
    ("regrade", "regrade 描述（应为判分重跑）"),
]

# 允许出现的白名单（历史对照表等）
ALLOW_CTX = ["难度演进", "历史", "v1.0.0 |", "| v2.0.0 |"]


def scan_text(label, text, path=""):
    hits = []
    for pat, why in OLD:
        if pat in text:
            # 查上下文是否为历史对照
            idx = text.find(pat)
            ctx = text[max(0, idx - 60): idx + 60].replace("\n", " ")
            if any(a in ctx for a in ALLOW_CTX) and pat in ("33 条", "S_max 179", "2.0.0", "3.0.0", "1.0.0", "v3.0.0"):
                continue
            hits.append((pat, why, ctx[:120]))
    if hits:
        print(f"\n  [{label}] {path}")
        for pat, why, ctx in hits:
            print(f"    ⚠ {pat}  ({why})")
            print(f"       …{ctx}…")
    return hits


print("=" * 96)
print("1) 题包本体（FIN3-WKN-152 文本文件）")
print("=" * 96)
total = 0
TXT_EXT = {".md", ".toml", ".json", ".py", ".sh", ".csv", ".txt", ".yaml", ".yml"}
for p in sorted(TASK.rglob("*")):
    if p.is_file() and p.suffix.lower() in TXT_EXT:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        h = scan_text("本体", t, str(p.relative_to(TASK)))
        total += len(h)

print()
print("=" * 96)
print("2) 批次目录（含交付文档、归档 reward/summary）")
print("=" * 96)
for p in sorted(BATCH.rglob("*")):
    if p.is_file() and p.suffix.lower() in TXT_EXT:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        h = scan_text("批次", t, str(p.relative_to(BATCH)))
        total += len(h)

print()
print("=" * 96)
print("3) 三个 zip 内部")
print("=" * 96)
for z in sorted(PKG.glob("*152*.zip")):
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith("/") or pathlib.Path(n).suffix.lower() not in TXT_EXT:
                continue
            try:
                t = zf.read(n).decode("utf-8", errors="replace")
            except Exception:
                continue
            h = scan_text(f"zip:{z.name}", t, n)
            total += len(h)

print()
print("=" * 96)
print(f"残留命中合计: {total} 处")
print("=" * 96)
sys.exit(1 if total else 0)
