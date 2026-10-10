# -*- coding: utf-8 -*-
"""审查 qwen/gpt 的 v3 交付物，挖掘『业务上应要求、但当前判据未覆盖或模型未做到』的点。
对照三处：题面 requirement（instruction 25 条）、当前 37 判据、模型实际交付。
"""
import json
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
Q = W / "harbor-weakness" / "_qc_runs"
OUT = {
    "qwen": Q / "g5-152v3-qwen" / "trials" / "qwen38max-152v3" / "artifacts" / "app" / "output",
    "gpt": Q / "g5-152v3-gpt" / "trials" / "gpt56sol-152v3" / "artifacts" / "app" / "output",
    "oracle": Q / "g4-152v3" / "trials" / "oracle-152v3" / "artifacts" / "app" / "output",
}
for ex, d in OUT.items():
    if not d.is_dir():
        print(f"缺 {ex}: {d}")
        continue
    print("=" * 104)
    print(f"{ex} 交付物")
    print("=" * 104)
    for f in sorted(d.iterdir()):
        if f.is_file():
            print(f"  {f.name:<45} {f.stat().st_size:>9,} B")

print()
print("=" * 104)
print("xlsx 工作表清单对比（题面要求 9 个模块）")
print("=" * 104)
for ex, d in OUT.items():
    x = d / "FIN3-WKN-152_ipo_model.xlsx"
    if x.exists():
        try:
            import openpyxl
            wb = openpyxl.load_workbook(x, read_only=True, data_only=True)
            print(f"  {ex:<7} {wb.sheetnames}")
            wb.close()
        except Exception as e:
            print(f"  {ex:<7} ERR {e}")

print()
print("=" * 104)
print("pricing_memo.md 结构对比（章节标题）")
print("=" * 104)
for ex, d in OUT.items():
    m = d / "FIN3-WKN-152_pricing_memo.md"
    if m.exists():
        t = m.read_text(encoding="utf-8", errors="replace")
        heads = re.findall(r"^(#{1,4})\s*(.+)$", t, re.M)
        n_cn = len(re.findall(r"[一-鿿]", t))
        print(f"  {ex:<7} {m.stat().st_size:>6,} B  中文字数≈{n_cn}")
        for h, txt in heads:
            print(f"      {h} {txt[:70]}")

print()
print("=" * 104)
print("source_trace.csv 内容对比（行数 / 表头）")
print("=" * 104)
for ex, d in OUT.items():
    s = d / "FIN3-WKN-152_source_trace.csv"
    if s.exists():
        t = s.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"  {ex:<7} {len(t)} 行 | 表头: {t[0][:150] if t else ''}")
        for l in t[1:]:
            print(f"        {l[:170]}")
