# -*- coding: utf-8 -*-
"""同步金标备忘录 .md（与 fix_golden.py 对 reproduce.py 的改动一致）。

处理对象：
  harbor-weakness/FIN3-WKN-150/solution/golden_output/…备忘录.md
  harbor-weakness/FIN3-WKN-150/tests/__golden_output/…备忘录.md
  harbor-weakness/work_fin-b01_20261006_fix3-150/跑分产物与轨迹/oracle/output/…备忘录.md

用法：python fix_golden_md.py [--dry-run]
"""
import os
import sys

REPO = r"C:\Users\Administrator\Desktop\wff-task"
TASK = os.path.join(REPO, "harbor-weakness", "FIN3-WKN-150")
MEMO = "FIN3-WKN-150_PreIPO投资决策备忘录.md"
TARGETS = [
    os.path.join(TASK, "solution", "golden_output", MEMO),
    os.path.join(TASK, "tests", "__golden_output", MEMO),
    os.path.join(TASK, "work_fin-b01_20261006_fix3-150", "跑分产物与轨迹", "oracle", "output", MEMO),
]

OLD_PROFIT = ("- **盈利能力**：毛利率稳定在 24.58%—25.38% 区间，期间费用率逐年上升，"
              "主因研发投入增加（研发费用率由 5.12% 升至 5.69%），属良性上升。")
NEW_PROFIT = ("- **盈利能力**：毛利率稳定在 24.58%—25.38% 区间；期间费用率总体呈下降趋势"
              "（14.02% → 13.62% → 13.38%），2026 年上半年小幅回升至 13.61%，"
              "主因研发投入持续增加（研发费用率由 5.12% 升至 5.69%），费用管控整体有效。")

OLD_CH7 = ("""约 **1.26 倍**（三年年化约 8.0%）。**回报空间有限，估值安全垫偏薄。**

## 八、风险提示与尽调缺口""")
NEW_CH7 = ("""约 **1.26 倍**（三年年化约 8.0%）。**回报空间有限，估值安全垫偏薄。**
- **投资执行与交割条件**：① 完成上述尽调缺口的补充与书面结论确认；② 就客户集中度、专利诉讼未决事项取得管理层专项说明；③ 完成估值上限的商务谈判并落实于正式投资协议；④ 业绩承诺与回购条款经法务复核后签署。
- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年承诺利润测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。

## 八、风险提示与尽调缺口""")

OLD_CH89 = ("""条件成熟后提交投资决策委员会审议。

## 九、交易执行与投后安排

- **交割条件**：① 完成上述尽调缺口的补充与书面结论确认；② 就客户集中度、专利诉讼未决事项取得管理层专项说明；③ 完成估值上限的商务谈判并落实于正式投资协议；④ 业绩承诺与回购条款经法务复核后签署。
- **投后监控指标**：按季度跟踪营业收入与扣非归母净利润（对照承诺值 15,000 / 18,000 万元）、第一大客户收入占比、应收账款周转天数、经营活动现金流净额与净现比；任一指标出现显著不利偏离时，启动估值调整或退出程序。
- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年承诺利润测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。
- **信息披露与合规**：本次投资决策相关材料、测算过程与本备忘录一并归档，全部结论均可追溯到材料包中的原始文件或指引条款，确保决策依据可复核、可审计。""")
NEW_CH89 = ("""条件成熟后提交投资决策委员会审议。

**投后监控指标**：按季度跟踪营业收入与扣非归母净利润（对照承诺值 15,000 / 18,000 万元）、第一大客户收入占比、应收账款周转天数、经营活动现金流净额与净现比；任一指标出现显著不利偏离时，启动估值调整或退出程序。

**信息披露与合规**：本次投资决策相关材料、测算过程与本备忘录一并归档，全部结论均可追溯到材料包中的原始文件或指引条款，确保决策依据可复核、可审计。""")

EDITS = [("期间费用率趋势", OLD_PROFIT, NEW_PROFIT),
         ("第七章并入交割/退出", OLD_CH7, NEW_CH7),
         ("第八章并入监控/披露 + 删第九章", OLD_CH89, NEW_CH89)]

dry = "--dry-run" in sys.argv
for path in TARGETS:
    print("=" * 84)
    rel = os.path.relpath(path, REPO)
    if not os.path.isfile(path):
        print(f"[缺失] {rel}")
        continue
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    original = text
    print(rel)
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 0:
            print(f"  [SKIP] {label}")
            continue
        text = text.replace(old, new)
        print(f"  [OK]   {label} ×{n}")
    han = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
    print(f"  章节数(## 一~九): {sum(text.count(f'## {c}、') for c in '一二三四五六七八九')}  汉字数: {han}")
    if not dry and text != original:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  已写入")
    elif dry:
        print("  （dry-run）")
