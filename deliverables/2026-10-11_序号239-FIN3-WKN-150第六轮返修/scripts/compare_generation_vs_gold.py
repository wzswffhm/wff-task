# -*- coding: utf-8 -*-
"""比对新生成 Oracle 产物与归档两份 golden，输出逐文件差异结论。"""
from __future__ import annotations

import difflib
import hashlib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-weakness" / "FIN3-WKN-150"
GEN = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
       / "evidence" / "oracle_generation" / "output")
PAIRS = [
    ("solution/golden_output", TASK / "solution" / "golden_output"),
    ("tests/__golden_output", TASK / "tests" / "__golden_output"),
]
REL = [
    "FIN3-WKN-150_PreIPO投资决策备忘录.md",
    "FIN3-WKN-150_reproduce.py",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart01_材料覆盖与数据缺口.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart02_收入与利润口径还原.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart03_现金流与营运效率.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart04_可比与DCF估值.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart05_估值区间与风险缺口.png",
]


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for label, base in PAIRS:
        print(f"=== {label} vs 新生成 ===")
        for rel in REL:
            a, b = base / rel, GEN / rel
            if not a.is_file():
                print(f"  [gold缺失] {rel}")
                continue
            same = sha(a) == sha(b)
            print(f"  {'一致' if same else '差异'}  {rel:66s} "
                  f"gold={a.stat().st_size:>8,} gen={b.stat().st_size:>8,}")
        print()

    print("=== memo 文本差异（gold vs 生成）===")
    gold = (TASK / "solution/golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md")
    gen = GEN / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
    ga = gold.read_text(encoding="utf-8").splitlines()
    gb = gen.read_text(encoding="utf-8").splitlines()
    diff = list(difflib.unified_diff(ga, gb, "gold", "generated", lineterm="", n=0))
    print(f"差异行数: {len(diff)}")
    for line in diff:
        print(line[:220])

    print("\n=== 生成 memo 占位符残留检查 ===")
    text = gen.read_text(encoding="utf-8")
    for token in ["{med_pe", "{fm(", "{stake_mid", "{multiple", "{irr", "{" + "promise"]:
        print(f"  {token!r:16s} 残留={token in text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
