# -*- coding: utf-8 -*-
"""修复 R30/R31 判据中的未定义量词「个别」（质检报告「序号 239」第 6 条）。

问题：锚点 4 用「个别判断」「个别处」表述，边界不可稳定复现。
处置：改为明确数量阈值（1 项 / 1 处），并同步 tests/rubrics.toml 与 rubrics.json
（两文件是设计态与运行态，必须一致；改动后须重新判分）。

用法：python fix_rubrics.py [--dry-run]
"""
import os
import sys

REPO = r"C:\Users\Administrator\Desktop\wff-task"
TASK = os.path.join(REPO, "harbor-weakness", "FIN3-WKN-150")
TOML = os.path.join(TASK, "tests", "rubrics.toml")
JSON = os.path.join(TASK, "rubrics.json")

R30_OLD = "4=四项齐备、个别判断缺明确支撑"
R30_NEW = "4=四项齐备、其中 1 项判断缺明确支撑"
R31_OLD = "4=总体一致、个别处表述不够明确"
R31_NEW = "4=总体一致、有 1 处表述不够明确"
# rubrics.json 的锚点映射键值对
J30_OLD = '"0.75": "四项齐备、个别判断缺明确支撑"'
J30_NEW = '"0.75": "四项齐备、其中 1 项判断缺明确支撑"'
J31_OLD = '"0.75": "总体一致、个别处表述不够明确"'
J31_NEW = '"0.75": "总体一致、有 1 处表述不够明确"'

dry = "--dry-run" in sys.argv
for path, edits in ((TOML, [(R30_OLD, R30_NEW, "R30 锚点4"), (R31_OLD, R31_NEW, "R31 锚点4")]),
                    (JSON, [(R30_OLD, R30_NEW, "R30 description"), (R31_OLD, R31_NEW, "R31 description"),
                            (J30_OLD, J30_NEW, "R30 锚点映射"), (J31_OLD, J31_NEW, "R31 锚点映射")])):
    print("=" * 80)
    rel = os.path.relpath(path, REPO)
    if not os.path.isfile(path):
        print(f"[缺失] {rel}")
        continue
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    original = text
    print(rel)
    for old, new, label in edits:
        n = text.count(old)
        if n == 0:
            print(f"  [SKIP] {label}（已修或无此串）")
            continue
        text = text.replace(old, new)
        print(f"  [OK]   {label} ×{n}")
    print(f"  '个别'残留: {text.count('个别')}")
    if not dry and text != original:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  已写入")
    elif dry:
        print("  （dry-run）")
