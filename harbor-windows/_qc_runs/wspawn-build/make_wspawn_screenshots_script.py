# -*- coding: utf-8 -*-
"""从 make_four_screenshots.py 派生一份只处理 wfflab__wspawn-218 的截图脚本。"""
from __future__ import annotations

import pathlib
import re

SRC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
                   r"\make_four_screenshots.py")
DST = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
                   r"\wspawn-build\make_wspawn_screenshots.py")

NEW = (
    "TASKS = {\n"
    '    "218": {"pkg": "wfflab__wspawn-218-v1.0.0-delivery", "id": "wfflab__wspawn-218",\n'
    '            "version": "1.0.0", "require": 14, "build": "wspawn-build"},\n'
    "}"
)


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    match = re.search(r"TASKS = \{.*?\n\}", text, re.S)
    if not match:
        raise SystemExit("未找到 TASKS 块")
    out = text[:match.start()] + NEW + text[match.end():]
    out = out.replace("make_four_screenshots.py", "make_wspawn_screenshots.py")
    out = out.replace("为 215/216/219/220 四个交付包生成", "为 wfflab__wspawn-218 生成")
    out = out.replace("python make_wspawn_screenshots.py            # 四包\n    python make_wspawn_screenshots.py 216        # 单包",
                      "python make_wspawn_screenshots.py")
    DST.write_text(out, encoding="utf-8")
    print(f"已写出 {DST}（{len(out)} bytes）")
    print(re.search(r"TASKS = \{.*?\n\}", out, re.S).group(0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
