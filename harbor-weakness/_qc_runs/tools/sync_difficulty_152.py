# -*- coding: utf-8 -*-
"""同步 task.toml：A3 → A2（实测落档）+ deliverables desc 九个→十个模块。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152\task.toml")
raw = P.read_text(encoding="utf-8")
edits = []


def rep(old, new, label):
    global raw
    n = raw.count(old)
    if n != 1:
        print(f"  [!!] {label}: 匹配 {n} 次")
        edits.append(False)
        return
    raw = raw.replace(old, new, 1)
    print(f"  [OK] {label}")
    edits.append(True)


print("=" * 90)
print("task.toml 同步（实测落档 A2）")
print("=" * 90)
rep('keywords = ["finance", "investment-banking", "A3"]',
    'keywords = ["finance", "investment-banking", "A2"]',
    "L17 keywords A3→A2")
rep('difficulty = "A3"',
    'difficulty = "A2"',
    "L27 difficulty A3→A2（实测 0.590643 ∈ [0.5,0.6)）")
rep('tags = ["finance", "investment-banking", "A3",',
    'tags = ["finance", "investment-banking", "A2",',
    "L39 tags A3→A2")
rep('desc = "主交付物：修复后的 IPO 模型，含 Inputs、QoE、Valuation、Sensitivity、Offering_Proceeds、Dilution、Pricing_Summary、Error_Audit、Source_Trace 九个模块"',
    'desc = "主交付物：修复后的 IPO 模型，含 Inputs、QoE、Valuation、Sensitivity、Offering_Proceeds、Dilution、Pricing_Summary、Error_Audit、Source_Trace、Tieout_Detail 十个模块"',
    "L43 deliverables desc 九→十个模块")

print()
if all(edits):
    P.write_text(raw, encoding="utf-8", newline="\n")
    print(f"[写出] {P}  {len(raw.encode('utf-8')):,} B")
else:
    print("[!!] 有失败，未写出")

# 校验
t = P.read_text(encoding="utf-8")
print()
print("=" * 90)
print("校验")
print("=" * 90)
import re
print(f"  difficulty: {re.search(r'difficulty = \"(\w+)\"', t).group(1)}")
print(f"  keywords 含 A2: {'\"A2\"' in t}   残留 A3: {'A3' in t}")
print(f"  version: {re.search(r'version = \"([^\"]+)\"', t).group(1)}")
print(f"  task_complexity: {re.search(r'task_complexity = \"(\w+)\"', t).group(1)}")
print(f"  Tieout_Detail 在 desc: {'Tieout_Detail' in t}")
