# -*- coding: utf-8 -*-
"""判据↔题面 泄漏比对：找出 rubrics 中被逐字/高度重叠写进 instruction.md 的段落。
目标：定位"题面告诉了判官会查什么"的地方（这是难度被泄掉的主因）。
"""
import pathlib
import re
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
ins = (TASK / "instruction.md").read_text(encoding="utf-8")
ins_lines = ins.splitlines()
crit = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))["criterion"]


def norm(s: str) -> str:
    s = re.sub(r"[`*#>|（）()：:；;、，,。.\s\-—/\\%\$\d]+", "", s)
    return s


def ngrams(s: str, n: int = 12):
    t = norm(s)
    return {t[i:i + n] for i in range(max(0, len(t) - n + 1))}


ins_norm_all = norm(ins)
ins_grams = ngrams(ins, 8)

print("=" * 104)
print("逐判据：与 instruction.md 的最长公共片段 / 覆盖率")
print("=" * 104)
print(f"{'ID':<6}{'重叠字数':>8}  {'覆盖率':>7}  最长片段 / instruction 行号")
print("-" * 104)

leaks = []
for c in crit:
    cid = c["id"]
    desc = c.get("description", "")
    # 只取描述主体（去掉 Deliverables to inspect）
    body = desc.split("Deliverables to inspect")[0]
    g = ngrams(body, 8)
    inter = g & ins_grams
    if not inter:
        print(f"{cid:<6}{0:>8}  {0:>7.1%}  —")
        continue
    # 最长连续片段：找 desc 中出现在 ins 的最长子串
    longest = max(inter, key=len)
    # 定位行号
    ln = []
    nn = norm(body)
    for i, l in enumerate(ins_lines, 1):
        ln_l = norm(l)
        if longest and longest in ln_l:
            ln.append(i)
        elif ln_l and any(ln_l[j:j + 10] in nn for j in range(max(1, len(ln_l) - 9))):
            if i not in ln:
                ln.append(i)
    cov = len(inter) / max(1, len(g))
    print(f"{cid:<6}{len(inter):>8}  {cov:>7.1%}  「{longest}」  行{ln[:4]}")
    if cov >= 0.10 or len(inter) >= 6:
        leaks.append((cid, cov, len(inter), longest, ln[:4]))

print()
print("=" * 104)
print(f"疑似泄漏判据（覆盖率≥10% 或重叠片段≥6）: {len(leaks)} 条")
print("=" * 104)
for cid, cov, n, frag, ln in sorted(leaks, key=lambda x: -x[1]):
    print(f"  {cid}  覆盖 {cov:.1%}  片段「{frag}」  instruction 行 {ln}")

print()
print("=" * 104)
print("instruction 中与判据强对应的『操作指南式』段落（人工复核用）")
print("=" * 104)
KEY = ["逐条列出", "文件、行或月份", "不少于", "逐表核验", "逐项", "至少覆盖",
       "全部", "必须", "须逐", "勾稽", "去重", "优先级", "量级", "待核实"]
for i, l in enumerate(ins_lines, 1):
    if any(k in l for k in KEY):
        print(f"  L{i}: {l.strip()[:190]}")
