# -*- coding: utf-8 -*-
"""把 pack_152_v4_fix.py 的批次第二层校验从「仅题目目录」改为 151 口径（三者平级）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\tools\pack_152_v4_fix.py")
raw = P.read_text(encoding="utf-8")

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

if "151 口径: 第二层三者平级" in raw:
    print("  [--] 已是 151 口径校验")
elif old_block in raw:
    raw = raw.replace(old_block, new_block, 1)
    P.write_text(raw, encoding="utf-8", newline="\n")
    print("  [OK] 批次第二层校验 -> 151 口径（三者平级）")
else:
    print("  [!!] 未定位校验块，需人工")
    sys.exit(1)
