# -*- coding: utf-8 -*-
"""更新第六轮交付文档生成脚本与 README：同步最新产物哈希并补记 R19 缺口的修复。"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
SIX = REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
TARGETS = [SIX / "scripts" / "build_delivery_doc_fix8.py", SIX / "README.md"]

OLD_R11 = ("3. **生成结果驱动的一处金标补全（R11 闭环）**：首次生成后重判发现 `R11`（扣非归母净利润还原）判 0"
           "——判据要求列示报告期**四期**非经常性损益（税后），而金标此前只出现 2025 年的 2,550。"
           "经核对《11_非经常性损益明细.csv》可由脚本算出 2023 年 1,564、2024 年 1,768、2025 年 2,550、"
           "2026 年上半年 1,088，遂在 `reproduce.py` 第四节补一句「报告期各期非经常性损益（税后）为……」，"
           "重新生成后四期数值齐备、`R11` 转为满分。该补全**只补列输入材料中已存在的数据**，不引入任何新参数。")

NEW_R11 = ("3. **生成结果驱动的两处金标补全（R11 / R19 闭环）**：逐轮重判把「判据明确要求、金标未明写」的缺陷逐处暴露并补齐——"
           "(a) `R11`（扣非归母净利润还原）要求列示报告期**四期**非经常性损益（税后），金标此前只有 2025 年的 2,550；"
           "核对《11_非经常性损益明细.csv》后补列 2023 年 1,564、2024 年 1,768、2025 年 2,550、2026 年上半年 1,088。"
           "(b) `R19`（净负债口径）要求**明确指出**货币资金总额与有息负债构成，金标此前只给受限额与合计；"
           "补写「货币资金总额 25,000 万元（使用受限 3,500 万元、可自由支配 21,500 万元）」与"
           "「有息负债 20,000 万元（短期借款 12,000 万元 + 长期借款 8,000 万元）」。"
           "两处补全**只把脚本已算出的、输入材料中已有的数据写入正文**，不改动任何结论数值、不引入新参数。")

REPLACEMENTS = [
    ("8823bab5d2f1", "ca70944e0c7d"),
    ("2fe0244cf125", "ca70944e0c7d"),
    ("2d1935c9a1fe", "84430a3d30ea"),
    ("ab21949dae8d", "84430a3d30ea"),
    ("16,800 B", "17,268 B"),
    ("17,006 B", "17,268 B"),
    (OLD_R11, NEW_R11),
    # 第 5 项证据列同步
    ("脚本两份逐字节一致（sha256 `ca70944e0c7d…`）；生成产物无任何 `{…}` 占位符残留；生成备忘录 17,268 B / "
     "sha256 `84430a3d30ea…`，与 `solution/golden_output`、`tests/__golden_output`、`oracle/output` "
     "**四处逐字节一致**；四期非经常性损益 1,564 / 1,768 / 2,550 / 1,088 与扣非归母 7,021 / 9,231 / 12,070 / "
     "6,137 均在文中；5 张 PNG 与既有 golden 逐字节相同",
     "脚本两份逐字节一致（sha256 `ca70944e0c7d…`）；生成产物无任何 `{…}` 占位符残留；生成备忘录 17,268 B / "
     "sha256 `84430a3d30ea…`，与 `solution/golden_output`、`tests/__golden_output`、`oracle/output` "
     "**四处逐字节一致**；四期非经常性损益 1,564 / 1,768 / 2,550 / 1,088、扣非归母 7,021 / 9,231 / 12,070 / "
     "6,137、货币资金总额 25,000（受限 3,500 / 可支配 21,500）与有息负债 20,000（短期 12,000 + 长期 8,000）"
     "均已明写；5 张 PNG 与既有 golden 逐字节相同"),
]


def main() -> int:
    for path in TARGETS:
        text = path.read_text(encoding="utf-8")
        changed = 0
        for old, new in REPLACEMENTS:
            if old in text:
                count = text.count(old)
                text = text.replace(old, new)
                changed += count
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{path.name}: {changed} 处替换")
        for token in ["84430a3d30ea", "ca70944e0c7d", "17,268 B", "R19", "25,000"]:
            print(f"    {token:14s} {token in text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
