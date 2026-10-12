# -*- coding: utf-8 -*-
"""判定哪份 golden 对应当前 v3 判据：对比 v3 oracle output / v3 qwen output 与三份 golden。"""
import hashlib
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = W / "harbor-weakness" / "FIN3-WKN-152"
Q = W / "harbor-weakness" / "_qc_runs"

CANDS = {
    "tests/__golden_output": TASK / "tests" / "__golden_output",
    "tests/__golden_output__": TASK / "tests" / "__golden_output__",
    "solution/golden_output": TASK / "solution" / "golden_output",
    "v3 oracle output": Q / "g4-152v3" / "trials" / "oracle-152v3" / "artifacts" / "app" / "output",
    "v3 qwen output": Q / "g5-152v3-qwen" / "trials" / "qwen38max-152v3" / "artifacts" / "app" / "output",
    "v3 gpt output": Q / "g5-152v3-gpt" / "trials" / "gpt56sol-152v3" / "artifacts" / "app" / "output",
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]

print("=" * 100)
print("三份 golden 与 v3 各执行体 output 的文件指纹对比")
print("=" * 100)
names = ["FIN3-WKN-152_ipo_model.xlsx", "FIN3-WKN-152_pricing_memo.md",
         "FIN3-WKN-152_reproduce.py", "FIN3-WKN-152_qoe_bridge.csv",
         "FIN3-WKN-152_source_trace.csv", "FIN3-WKN-152_valuation_matrix.csv",
         "FIN3-WKN-152_charts.png"]
hdr = f"{'文件':<44}" + "".join(f"{k.split('/')[-1][:16]:>18}" for k in CANDS)
print(hdr)
print("-" * len(hdr))
for n in names:
    row = f"{n[:43]:<44}"
    for label, d in CANDS.items():
        f = d / n
        row += f"{(sha(f) if f.exists() else '-'):>18}"
    print(row)

print()
print("=" * 100)
print("文件大小对比（判断哪份是最新 golden）")
print("=" * 100)
print(hdr)
print("-" * len(hdr))
for n in names:
    row = f"{n[:43]:<44}"
    for label, d in CANDS.items():
        f = d / n
        row += f"{(f'{f.stat().st_size:,}' if f.exists() else '-'):>18}"
    print(row)

print()
print("=" * 100)
print("solution/golden_output == tests/__golden_output__ 逐字节？")
print("=" * 100)
a = TASK / "solution" / "golden_output"
b = TASK / "tests" / "__golden_output__"
c = TASK / "tests" / "__golden_output"
for label, x, y in [("solution vs __golden_output__", a, b),
                    ("solution vs __golden_output", a, c),
                    ("__golden_output__ vs __golden_output", b, c)]:
    same = all(sha(x / n) == sha(y / n) for n in names if (x / n).exists() and (y / n).exists())
    print(f"  {label}: {'一致' if same else '不一致'}")

print()
print("=" * 100)
print("判据是否引用 golden 目录 / test.sh 如何用 golden")
print("=" * 100)
for f in ["tests/test.sh", "tests/finalize.py"]:
    p = TASK / f
    if p.exists():
        t = p.read_text(encoding="utf-8", errors="replace")
        for i, l in enumerate(t.splitlines(), 1):
            if "golden" in l.lower():
                print(f"  {f}:{i}: {l.strip()[:150]}")
