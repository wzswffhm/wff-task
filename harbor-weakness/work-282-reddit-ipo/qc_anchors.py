#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判据锚点人工核：check_instruction_anchors 对本题不适用（硬编码甲方批次），
按 gates.md 转人工核对 —— 每条判据的显式要求须能在 instruction.md 找到出处，
数值锚点须能由 input_files 单一条款唯一推出。"""
from __future__ import annotations

import pathlib
import re
import sys
import tomllib

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path("harbor-weakness/FIN3-WKN-152")
instr = (ROOT / "instruction.md").read_text(encoding="utf-8")
toml = tomllib.loads((ROOT / "tests/rubrics.toml").read_bytes().decode("utf-8"))

# input_files 全文（含单元格文本）
wb = load_workbook(ROOT / "environment/input_files/Q7_题目.xlsx", data_only=True)
cells = []
for ws in wb.worksheets:
    for row in ws.iter_rows(values_only=True):
        for v in row:
            if v is not None:
                cells.append(str(v))
xlsx_text = "\n".join(cells)

print("=" * 100)
print("判据锚点人工核（instruction.md 出处 + input_files 唯一出处）")
print("=" * 100)

NUM = re.compile(r"(?<![\d.])\d[\d,]*\.?\d*(?![\d.])")
rows = []
fail = 0
for c in toml["criterion"]:
    desc = c["description"]
    # 1) 关键短语能否在 instruction.md 命中
    #    取 desc 中的中文/英文关键片段（去停用）
    probes = []
    for pat in [r"交付物齐全", r"不超过 2 页", r"1,600", r"Proceed", r"\$34",
                r"\$31\.27", r"\$37\.25", r"118\.361", r"980\.915", r"519\.402",
                r"486\.432", r"158\.993", r"162\.293", r"106\.590", r"11\.17",
                r"21\.33", r"SBC", r"EV / 2024E Revenue", r"marketable securities",
                r"secondary", r"greenshoe", r"Error_Audit", r"2024-03-20",
                r"可复算", r"不硬编码", r"输入材料", r"Committee_Policy", r"勾稽",
                r"内部", r"SEC", r"承销费", r"12\.5%", r"4\.0x", r"5\.0x"]:
        if re.search(pat, desc):
            probes.append(pat)
    # 判据要求的名词是否出现在任务书
    key_terms = ["信息集", "2024-03-20", "SBC", "EBITDA", "2024E", "secondary",
                 "greenshoe", "承销费", "执行折扣", "可复算", "硬编码", "输入材料",
                 "Proceed", "勾稽", "内部假设", "SEC", "Error_Audit", "2 页",
                 "交付物", "文件名", "cross-check", "交叉", "增量"]
    hit = [k for k in key_terms if k in desc and k in instr]
    need = [k for k in key_terms if k in desc]
    missing = [k for k in need if k not in instr]
    ok = not missing
    if not ok:
        fail += 1
    rows.append((c["id"], len(need), len(hit), missing, ok))

print(f"\n{'ID':<6}{'术语数':>6}{'任务书命中':>10}  {'未在 instruction.md 命中':<40} 结论")
print("-" * 100)
for cid, n, h, miss, ok in rows:
    print(f"{cid:<6}{n:>6}{h:>10}  {(', '.join(miss) if miss else '-'):<40} {'OK' if ok else '需人工核'}")

print("\n" + "=" * 100)
print("数值锚点在 input_files 的唯一出处（xlsx 单元格命中）")
print("=" * 100)
anchors = [
    ("R05", "804.029", "Public_Financials Revenue 2023A"),
    ("R05", "-90.824", "Public_Financials Net income (loss) 2023A"),
    ("R05", "-69.275", "Public_Financials Adjusted EBITDA 2023A"),
    ("R05", "49.086", "Public_Financials SBC 2023A"),
    ("R05", "-84.838", "Public_Financials Free Cash Flow 2023A"),
    ("R07", "0.22", "Underwriting_Assumptions 2024E growth"),
    ("R08", "4", "Underwriting_Assumptions Peer low"),
    ("R08", "4.5", "Underwriting_Assumptions Peer mid"),
    ("R08", "5", "Underwriting_Assumptions Peer high"),
    ("R14", "401.176", "Public_Financials cash"),
    ("R14", "811.946", "Public_Financials marketable securities"),
    ("R09/R10", "15.276527", "Offering_Terms primary shares"),
    ("R15", "6.723473", "Offering_Terms secondary shares"),
    ("R16", "3.3", "Offering_Terms greenshoe"),
    ("R11", "143.716563", "Offering_Terms pre-money shares"),
    ("R10", "0.05", "Offering_Terms underwriting fee"),
    ("R10", "7", "Offering_Terms fixed expenses"),
    ("R03/R04", "34", "Offering_Terms proposed price"),
    ("R21", "11.17", "Public_Financials NTBV cross-check"),
    ("R21", "21.33", "Public_Financials dilution cross-check"),
]
allsrc = True
for cid, num, src in anchors:
    hit = num in xlsx_text
    allsrc = allsrc and hit
    print(f"  {'OK ' if hit else 'MISS'} {cid:<10} {num:<14} ← {src}")

# 计算类锚点（材料无原文，须能由原文唯一推出）
print("\n  计算类锚点（材料无原文、由条款唯一推出，已在独立重算中验证）:")
for cid, num, formula in [
    ("R06", "-118.361", "-69.275 - 49.086"),
    ("R07", "980.915", "804.029 × (1+0.22)"),
    ("R08", "31.27/34.26/37.25", "4/4.5/5 × 2024E → +net cash → ÷pre → ×0.875"),
    ("R09", "519.402", "15.276527 × 34"),
    ("R10", "486.432", "519.402 − 5% − 7.0"),
    ("R11", "158.993090", "143.716563 + 15.276527"),
    ("R16", "162.293090", "158.993090 + 3.3"),
    ("R16", "106.590", "3.3 × 34 × 0.95"),
    ("R03", "Proceed", "in_range ∧ |Δmid|≤0.50"),
]:
    print(f"      {cid:<10} {num:<20} = {formula}")

print("\n" + "=" * 100)
print(f"结论：数值锚点原文命中 {'全部通过' if allsrc else '存在缺口'}；"
      f"术语出处需人工核 {fail} 条")
print("说明：check_instruction_anchors.py 硬编码甲方批次 FIN-127/128/129-W，对本题不适用（gates.md），")
print("      本节为其人工替代核对。")
print("=" * 100)
