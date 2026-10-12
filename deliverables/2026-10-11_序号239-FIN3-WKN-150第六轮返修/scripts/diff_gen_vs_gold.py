# -*- coding: utf-8 -*-
"""比对脚本实际生成产物与归档金标（memo），逐行输出差异。"""
import difflib
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
GOLD = REPO / "harbor-weakness/FIN3-WKN-150/solution/golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md"
GOLD2 = REPO / "harbor-weakness/FIN3-WKN-150/tests/__golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md"
GEN = (REPO / "deliverables/2026-10-11_序号239-FIN3-WKN-150第六轮返修/evidence/_gen_check"
       / "FIN3-WKN-150_PreIPO投资决策备忘录.md")


def read(p: pathlib.Path) -> list[str]:
    return p.read_text(encoding="utf-8").splitlines()


def main() -> int:
    for label, path in [("gold(solution)", GOLD), ("gold(tests)", GOLD2), ("generated", GEN)]:
        txt = path.read_text(encoding="utf-8")
        print(f"{label:16s} bytes={path.stat().st_size:6d} chars={len(txt):6d} lines={len(txt.splitlines())}")
    print()
    a, b = read(GOLD), read(GEN)
    diff = list(difflib.unified_diff(a, b, "gold", "generated", lineterm="", n=1))
    print(f"=== gold vs generated 差异行数: {len(diff)} ===")
    for line in diff[:200]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
