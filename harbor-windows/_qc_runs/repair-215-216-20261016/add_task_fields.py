# -*- coding: utf-8 -*-
"""按 2026-10-16 质检指南补齐 task.toml 的 [task] 段字段。

指南速查表的配置卡点：
  * [task] 段的 authors 必须是 Author 对象数组（authors = [{ name = "..." }]），
    写成字符串数组会导致解析 taskconfig 报错。
  * keywords 与 tags 保持一致，供知识树关联使用。

本脚本在 [task] 段内补 authors / keywords（幂等）。
"""
from __future__ import annotations

import pathlib
import re

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
PKGS = {
    "wfflab__wsparse-215-v1.0.1-delivery": [
        "Windows", "NTFS", "sparse-file", "preallocation", "disk-usage",
        "DeviceIoControl", "Python",
    ],
    "wfflab__wvas-216-v1.0.1-delivery": [
        "Windows", "virtual-memory", "address-space", "VirtualQueryEx",
        "GetMappedFileNameW", "process-audit", "Python",
    ],
}

AUTHORS = 'authors = [{ name = "wfflab" }]'


def main() -> int:
    for pkg, keywords in PKGS.items():
        path = HW / pkg / "task.toml"
        text = path.read_text(encoding="utf-8")
        if "authors =" in text:
            print(f"{pkg}: 已有 authors，跳过")
            continue
        kw_line = "keywords = [" + ", ".join(f'"{k}"' for k in keywords) + "]"

        # 插到 [task] 段的 version 之后，保持可读顺序
        pattern = re.compile(r"(^\[task\]\n(?:.*\n)*?version = \"[^\"]+\"\n)", re.M)
        m = pattern.search(text)
        if not m:
            print(f"{pkg}: 未找到 [task] 段的 version 行，未修改")
            continue
        insert = AUTHORS + "\n" + kw_line + "\n"
        text = text[:m.end(1)] + insert + text[m.end(1):]
        path.write_text(text, encoding="utf-8")
        print(f"{pkg}: 已插入 authors / keywords")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
