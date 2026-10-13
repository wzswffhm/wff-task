# -*- coding: utf-8 -*-
"""bump_219_v12_docs.py -- 把 219 v1.2.0 的文档标题/计数从 1.1.0 更新到 1.2.0。

只改"当前版本陈述"，保留历史对照（v1.0.0 → v1.1.0 的整改记录）。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
         r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.2.0-delivery")

EDITS = [
    ("verifier/ISOLATION.md", [
        ("# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.1.0）",
         "# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.2.0）"),
        ("口径版本：**isolation-adaptation-v2（2026-10-13）**。",
         "口径版本：**isolation-adaptation-v3（2026-10-13）**。"),
    ]),
    ("verifier/WINDOWS_VALUE.md", [
        ("# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.1.0）",
         "# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.2.0）"),
        ("与 v1.1.0 的整改记录并列归档。",
         "与 v1.1.0 / v1.2.0 的整改记录并列归档。"),
    ]),
    ("verifier/README.md", [
        ("# 判分侧材料（wfflab__wpeimg-219，task version 1.1.0）",
         "# 判分侧材料（wfflab__wpeimg-219，task version 1.2.0）"),
        ("- `task_version = 1.1.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、",
         "- `task_version = 1.2.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、"),
        ("- required testcase 共 **27** 条：F2P 19 条 / P2P 8 条；全过为 1，否则为 0，\n  required 缺失或未终态一律 INVALID。",
         "- required testcase 共 **34** 条：F2P 26 条 / P2P 8 条；全过为 1，否则为 0，\n"
         "  required 缺失或未终态一律 INVALID。\n"
         "  > 34 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；\n"
         "  > 扩大颗粒度是本轮为拉开主模型区分度而做的有意选择，见 `REFIT-2026-10-13.md` §R8。"),
        ("check id（恒判 FAIL）；1.1.0 已删除该条目。",
         "check id（恒判 FAIL）；1.1.0 已删除该条目。\n"
         "- 1.2.0 新增两个程序化评分组：`data-directories`（0.08，4 条）与\n"
         "  `authenticode-detection`（0.06，3 条），对应题面新增的 A2 节。"),
    ]),
    ("verifier/evidence/README.md", [
        ("# 219 权威证据索引（task version 1.1.0）",
         "# 219 权威证据索引（task version 1.2.0）"),
        ("| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.1.0 与 v1.0.0 的样本**逐字节相同**，未改动） |",
         "| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.2.0、v1.1.0 与 v1.0.0 的样本**逐字节相同**，未改动） |"),
    ]),
]


def main() -> int:
    failures = []
    for rel, pairs in EDITS:
        p = D / rel.replace("/", "\\")
        text = io.open(p, encoding="utf-8").read()
        for old, new in pairs:
            if old not in text:
                failures.append("%s: pattern not found -> %s" % (rel, old[:60]))
                continue
            text = text.replace(old, new, 1)
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        print("updated", rel)
    for f in failures:
        print("MISS", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
