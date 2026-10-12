# -*- coding: utf-8 -*-
"""第二轮文档同步：最新产物哈希（R32 修复后）与 R32 补记。"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
SIX = REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
BUILD = SIX / "scripts" / "build_delivery_doc_fix8.py"
README = SIX / "README.md"

BUILD_PAIRS = [
    ("84430a3d30ea", "72b47a936dd9"),
    ("ca70944e0c7d", "8fbdca952fc3"),
    ("17,268 B", "17,312 B"),
    ("生成结果驱动的两处金标补全（R11 / R19 闭环）",
     "生成结果驱动的三处参考实现修正（R11 / R19 / R32 闭环）"),
    ("两处补全**只把脚本已算出的、输入材料中已有的数据写入正文**，不改动任何结论数值、不引入新参数。",
     "(c) `R32`（不硬编码结论）要求由脚本从输入材料计算出结论数值，原脚本把总股本 12,000 万股与"
     "第一大客户占比 36% 写成常量；现改为总股本从《34_股权结构、期权池与历史融资.md》股权结构表的"
     "合计行读取、客户集中度从《23_收入明细_分客户_2025.csv》按营业收入降序计算"
     "（口径不变，结果仍为 12,000 万股与 36.0%）。三处修正**只把脚本已算出的、输入材料中已有的"
     "数据写入正文或改为读入**，不改动任何结论数值、不引入新参数。"),
]

README_PAIRS = [
    ("生成反馈驱动的两处补全", "生成反馈驱动的三处补全"),
    ("两处补全只把脚本已算出的输入数据写入正文，不改结论数值、不引入新参数。",
     "(c) `R32` 判 0——判据要求脚本从输入计算结论数值，原脚本把总股本 12,000 万股与第一大客户占比 36% 写成常量；"
     "现改为总股本从《34_股权结构、期权池与历史融资.md》股权结构表合计行读取、客户集中度从"
     "《23_收入明细_分客户_2025.csv》按营业收入降序计算（结果不变：12,000 万股 / 36.0%）。"
     "三处补全只把脚本已算出的输入数据写入正文或改为读入，不改结论数值、不引入新参数。"),
    ("sha256 `ca70944e0c7d…`", "sha256 `8fbdca952fc3…`"),
    ("**真实生成**", "**真实生成**"),
    ("17,268 B / sha256 `84430a3d30ea…`", "17,312 B / sha256 `72b47a936dd9…`"),
]


def apply(path: pathlib.Path, pairs: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    changed = 0
    for old, new in pairs:
        if old in text and old != new:
            changed += text.count(old)
            text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"{path.name}: {changed} 处替换")
    for token in ["72b47a936dd9", "8fbdca952fc3", "17,312 B", "R32", "34_股权结构"]:
        print(f"    {token:16s} {token in text}")


def main() -> int:
    apply(BUILD, BUILD_PAIRS)
    apply(README, README_PAIRS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
