# -*- coding: utf-8 -*-
"""从共享的 generate_quality_review.py 派生一份只处理 wfflab__wspawn-218 的生成脚本。"""
from __future__ import annotations

import pathlib
import re

SRC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
                   r"\generate_quality_review.py")
DST = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
                   r"\wspawn-build\generate_wspawn_quality_review.py")

NEW = (
    "PACKAGES = [\n"
    '    {"num": "218", "pkg": "wfflab__wspawn-218-v1.0.0-delivery", '
    '"build": "wspawn-build", "mod": "wspawn"},\n'
    "]"
)


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    match = re.search(r"PACKAGES = \[.*?\n\]", text, re.S)
    if not match:
        raise SystemExit("未找到 PACKAGES 块")
    out = text[:match.start()] + NEW + text[match.end():]
    out = out.replace("generate_quality_review.py", "generate_wspawn_quality_review.py")
    DST.write_text(out, encoding="utf-8")
    print(f"已写出 {DST}（{len(out)} bytes）")
    print(re.search(r"PACKAGES = \[.*?\n\]", out, re.S).group(0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
