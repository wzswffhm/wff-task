# -*- coding: utf-8 -*-
"""由 v3 跑分脚本生成 v4 版本（trial 名与输出目录改为 v4）。"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs")

# (源, 目标)
PAIRS = [
    ("g4_v3_run.sh", "g4_v4_run.sh"),
    ("g5_v3_run.sh", "g5_v4_run.sh"),
    ("g5_v3_opus_run.sh", "g5_v4_opus_run.sh"),
    ("start_g4_v3.sh", "start_g4_v4.sh"),
    ("start_g5_v3.sh", "start_g5_v4.sh"),
    ("start_g5_v3_opus.sh", "start_g5_v4_opus.sh"),
]

print("=" * 92)
print("生成 v4 跑分脚本")
print("=" * 92)
for src, dst in PAIRS:
    s = Q / src
    if not s.exists():
        print(f"  [SKIP] 缺源 {src}")
        continue
    t = s.read_text(encoding="utf-8")
    o = t
    # trial 名 / 输出目录 / unit 名
    o = o.replace("152v3", "152v4")
    o = o.replace("v3.", "v4.")
    o = o.replace("v3 ", "v4 ")
    o = o.replace("G5 v3", "G5 v4")
    o = o.replace("g5-v3-", "g5-v4-")
    o = o.replace("g4-152v4", "g4-152v4")  # 已替换
    # 日志/描述里的版本
    o = o.replace("FIN3-WKN-152 v4.0.0", "FIN3-WKN-152 v4.0.0")
    if o == t:
        print(f"  [--] {dst}: 无变化（源可能已是 v4）")
    d = Q / dst
    d.write_text(o, encoding="utf-8", newline="\n")
    print(f"  [OK] {src} -> {dst}  ({len(o)} B)")

# 关键参数复核
print()
print("=" * 92)
print("v4 关键参数")
print("=" * 92)
for f in ["g4_v4_run.sh", "g5_v4_run.sh", "g5_v4_opus_run.sh"]:
    p = Q / f
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    for pat in [r"--trial-name\s+\S+", r"g5-152v4-\w+|g4-152v4", r"-m\s+\S+", r"-a\s+\S+"]:
        m = re.findall(pat, t)
        if m:
            print(f"  {f}: {' | '.join(sorted(set(m)))}")
    if "v3" in t:
        print(f"  [!!] {f} 仍含 v3 字样")
    print()

# 汇总：v4 的输出目录
print("v4 输出目录：")
for d in ["g4-152v4", "g5-152v4-qwen", "g5-152v4-gpt", "g5-152v4-opus"]:
    print(f"  {Q / d}")
