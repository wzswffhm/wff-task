# -*- coding: utf-8 -*-
"""核验修复后的金标：md 差异、图表差异、第四节桥接表、字数。"""
import difflib
import hashlib
import pathlib
import re
import sys

GOLD = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006_fix6-150\FIN3-WKN-150\solution\golden_output")
GEN = pathlib.Path(r"C:\Users\Administrator\.wff-creds\w150\out")

a = (GEN / "FIN3-WKN-150_PreIPO投资决策备忘录.md").read_text(encoding="utf-8").splitlines()
b = (GOLD / "FIN3-WKN-150_PreIPO投资决策备忘录.md").read_text(encoding="utf-8").splitlines()
print("=== 备忘録 diff（generated vs golden） ===")
for line in difflib.unified_diff(b, a, "golden", "generated", lineterm="", n=2):
    print(line)

print("\n=== 图表哈希 ===")
for f in sorted((GOLD / "FIN3-WKN-150_charts").iterdir()):
    t = GEN / "FIN3-WKN-150_charts" / f.name
    h1 = hashlib.sha256(f.read_bytes()).hexdigest()[:12]
    h2 = hashlib.sha256(t.read_bytes()).hexdigest()[:12]
    print(f"{f.name[:44]:46} {'SAME' if h1 == h2 else 'DIFF'}")

print("\n=== 新备忘録第四节 ===")
txt = (GEN / "FIN3-WKN-150_PreIPO投资决策备忘录.md").read_text(encoding="utf-8")
sec = txt.split("## 四、利润口径还原")[1].split("## 五、")[0]
print(sec.strip())

print("\n=== 字数（中文字符+中文标点，去表格竖线与代码块） ===")
body = re.sub(r"```.*?```", "", txt, flags=re.S).replace("|", "")
print(len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", body)))

print("\n=== 桥接表数值校验 ===")
kf = 12070
nrec = 2550
tax, intexp, da, sbp = 2580, 420, 6500, 620
print("扣非+非经常性+所得税+利息+D&A+股份支付 =", kf + nrec + tax + intexp + da + sbp)
print("净利润+所得税+利息+D&A+股份支付        =", 14620 + tax + intexp + da + sbp)
