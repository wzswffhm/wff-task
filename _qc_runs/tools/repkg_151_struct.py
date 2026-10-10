# -*- coding: utf-8 -*-
"""把 pack_152_v4_fix.py 的批次第二层校验从「仅题目目录」改为 151 口径（三者平级），随后重打包。"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\tools\pack_152_v4_fix.py")
raw = P.read_text(encoding="utf-8")

# 1) report(): 批次 zip 校验改为「第二层 == 三者」
old_block = '''    if want_second:
        if label == "批次 zip":
            if second != [want_second]:
                ok = False
                print(f"  [!!] 第二层应仅 [{want_second}]，实际 {second}")
        elif want_second not in second:
            ok = False'''
new_block = '''    if want_second:
        if label == "批次 zip":
            # 151（序号267，一审通过）口径：批次根三者平级
            expect = sorted([want_second, "交付文档.md", "跑分产物与轨迹"])
            if second != expect:
                ok = False
                print(f"  [!!] 第二层应为 {expect}（151 口径），实际 {second}")
            else:
                print(f"  151 口径: 第二层三者平级 ✓")
        elif want_second not in second:
            ok = False'''
if old_block in raw:
    raw = raw.replace(old_block, new_block, 1)
    print("  [OK] report 批次第二层校验 -> 151 口径")
else:
    print("  [!!] 未定位 report 校验块")

P.write_text(raw, encoding="utf-8", newline="\n")

# 2) 重打包
print()
print("=" * 94)
print("重打包")
print("=" * 94)
import subprocess
r = subprocess.run(
    [sys.executable, str(P)],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    env={"PYTHONIOENCODING": "utf-8", "PATH": ";".join(sys.path and [] or []) or None},
)
print(r.stdout)
if r.stderr.strip():
    print("STDERR:", r.stderr[:500])
print(f"exit={r.returncode}")
