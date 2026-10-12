# -*- coding: utf-8 -*-
"""审查 152 题面红线：答案是否写在题面上、是否有引导性注释；并看 v3 新增判据。"""
import re
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
INS = (TASK / "instruction.md").read_text(encoding="utf-8")

print("=" * 100)
print("1) instruction.md 中疑似『直接给出结论/答案』的句子")
print("=" * 100)
lines = INS.splitlines()
# 已知结论锚点（来自质检报告 §四.2 独立重算）
ANSWERS = ["-118.361", "980.915", "1,213.122", "1213.122", "31.27", "34.26", "37.25",
           "519.402", "486.432", "158.993", "162.293", "106.590", "Proceed", "Reprice",
           "Defer", "11.17", "21.33", "EV / 2024E Revenue", "EV/2024E Revenue"]
for i, l in enumerate(lines, 1):
    for a in ANSWERS:
        if a in l:
            print(f"  L{i} [{a}]: {l.strip()[:200]}")
            break

print()
print("=" * 100)
print("2) 疑似『引导性注释 / 解题提示 / 坑位提醒』")
print("=" * 100)
HINT = ["注意：", "提示：", "小心", "别忘了", "这里有个", "坑", "易错", "常见错误",
        "应避免", "正确做法", "应该是", "正确答案", "参考答案", "标准答案",
        "rubric", "判据", "评分", "golden", "score", "threshold"]
for i, l in enumerate(lines, 1):
    low = l.lower()
    for h in HINT:
        if h.lower() in low:
            print(f"  L{i} [{h}]: {l.strip()[:220]}")
            break

print()
print("=" * 100)
print("3) input_files 中是否有『答案』类文件（题面泄露通道）")
print("=" * 100)
inf = TASK / "environment" / "input_files"
if inf.exists():
    fs = sorted(p.relative_to(inf).as_posix() for p in inf.rglob("*") if p.is_file())
    print(f"  共 {len(fs)} 个文件")
    suspicious = [f for f in fs if any(k in f.lower() for k in
                  ("answer", "solution", "golden", "expected", "result", "结论", "答案", "评分"))]
    print(f"  可疑名: {suspicious or '无'}")
else:
    print("  目录不存在")

print()
print("=" * 100)
print("4) v3 新增判据（R28~R37）内容")
print("=" * 100)
import tomllib
t = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
crit = t.get("criterion", [])
for c in crit:
    cid = c.get("id", "")
    if cid in ("R28", "R29", "R30", "R31", "R32", "R33", "N01", "N02", "N03", "N04"):
        desc = c.get("description", "").replace("\n", " ")
        print(f"  {cid} w={c.get('weight')} negate={c.get('negate')}")
        print(f"      {desc[:400]}")
