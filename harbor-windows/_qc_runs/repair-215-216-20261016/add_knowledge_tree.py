# -*- coding: utf-8 -*-
"""给两包 task.toml 的 [task] 段补知识树路径（L1/L2/L3）。

依据 2026-10-16 质检指南 2.5 与速查表：
  ⛔ task.toml 必须包含完整知识树路径（L1/L2/L3），缺失/层级不全/节点非法
     → 驳回；且路径要与 tags/keywords 自洽。
L1 取 references/02-windows-value.md 的 12 个主流方向名（真实存在的节点）；
L2/L3 按该文件给出的"代表性能力"细化，并与包内 tags 对齐。
"""
from __future__ import annotations

import pathlib
import re

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
TREES = {
    "wfflab__wsparse-215-v1.0.1-delivery": {
        "l1": "文件系统与路径",
        "l2": "NTFS 存储语义",
        "l3": "稀疏文件与簇分配",
    },
    "wfflab__wvas-216-v1.0.1-delivery": {
        "l1": "进程与执行上下文",
        "l2": "进程内存与地址空间",
        "l3": "虚拟内存查询与映射审计",
    },
}


def main() -> int:
    for pkg, tree in TREES.items():
        path = HW / pkg / "task.toml"
        text = path.read_text(encoding="utf-8")
        if "knowledge_tree" in text:
            print(f"{pkg}: 已有 knowledge_tree，跳过")
            continue
        line = ('knowledge_tree = ["%s", "%s", "%s"]\n'
                % (tree["l1"], tree["l2"], tree["l3"]))
        pattern = re.compile(r"(^\[task\]\n(?:.*\n)*?version = \"[^\"]+\"\n)", re.M)
        m = pattern.search(text)
        if not m:
            print(f"{pkg}: 未找到 [task] version 行")
            continue
        text = text[:m.end(1)] + line + text[m.end(1):]
        path.write_text(text, encoding="utf-8")
        print(f"{pkg}: 已插入 knowledge_tree = {tree['l1']} / {tree['l2']} / {tree['l3']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
