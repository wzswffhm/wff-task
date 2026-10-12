# -*- coding: utf-8 -*-
"""逐条核对 36 条判据中出现的具体数值是否已在金标备忘录中明写。

用途：R11（四期非经常性损益）、R19（货币资金总额与有息负债拆分）均属
"判据明确要求、金标未写明"的真实缺陷。本脚本一次性列出同类候选，
避免逐轮重判（每轮约 40 分钟）才发现下一处。
"""
from __future__ import annotations

import pathlib
import re
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-weakness" / "FIN3-WKN-150"
MEMO = TASK / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
OUT = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
       / "evidence" / "rubric_value_scan.md")

# 形如 25,000 / 1,500 / 6.50% / 16.12，且带千分位或长度>=4 的才可能是"具体口径数值"
NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2,}|\d{3,}")


def main() -> int:
    rubric = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
    memo = MEMO.read_text(encoding="utf-8")
    lines: list[str] = ["# 判据数值对照扫描（金标未明写的候选）", ""]
    total_missing = 0

    for item in rubric["criterion"]:
        rid = item["id"]
        desc = item["description"]
        body = desc.split("Deliverables to inspect:")[0]
        # 容差/区间说明里的数字不作为"必须明写"的要求
        numbers: list[str] = []
        for token in NUM.findall(body):
            if token in numbers:
                continue
            numbers.append(token)
        missing = [n for n in numbers if n not in memo]
        if missing:
            total_missing += len(missing)
            lines.append(f"## {rid}（weight={item.get('weight')}, negate={item.get('negate')}）")
            lines.append("")
            lines.append(f"- 未在备忘录中出现的数值：{', '.join(missing)}")
            for n in missing:
                # 给出该数字所在的上下文片段，便于判断是否属真实要求
                idx = body.find(n)
                snippet = body[max(0, idx - 60):idx + 30].replace("\n", " ")
                lines.append(f"    - `{n}` … {snippet}…")
            lines.append("")

    if total_missing == 0:
        lines.append("全部判据数值均已在备忘录中出现。")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"\n未出现数值合计: {total_missing} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
