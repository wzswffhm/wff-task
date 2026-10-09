# -*- coding: utf-8 -*-
"""修复 FIN3-WKN-150 金标生成脚本的两处缺陷（质检报告「序号 239」第 4、5 条）。

1) 第 5 条：正文写「期间费用率逐年上升」，与表中 14.02%→13.62%→13.38%→13.61% 矛盾
   → 改为「总体呈下降趋势（…），2026 年上半年小幅回升至 …」，数值全部由 quality 动态取值
2) 第 4 条：金标多出「九、交易执行与投后安排」，违反题面/template_memo.md「八章不得增删」硬约束
   → 删除该章标题，内容按其语义并入既有章节：
       交割条件 / 退出安排      → 第七章（估值结论与交易方案）
       投后监控指标 / 信息披露  → 第八章（风险提示与尽调缺口）
   （直接删除会使金标汉字数跌破 R03 的 3,500 下限，故必须并入而非删除）

同步两份 golden：solution/golden_output 与 tests/__golden_output。
用法：python fix_golden.py [--dry-run]
"""
import os
import sys

REPO = r"C:\Users\Administrator\Desktop\wff-task"
TASK = os.path.join(REPO, "harbor-weakness", "FIN3-WKN-150")
TARGETS = [
    os.path.join(TASK, "solution", "golden_output", "FIN3-WKN-150_reproduce.py"),
    os.path.join(TASK, "tests", "__golden_output", "FIN3-WKN-150_reproduce.py"),
]

EDIT_PROFIT = (
    """A(f'- **盈利能力**：毛利率稳定在 {min(quality[y]["gm"] for y in YEARS) * 100:.2f}%—'
  f'{max(quality[y]["gm"] for y in YEARS) * 100:.2f}% 区间，期间费用率逐年上升，'
  '主因研发投入增加（研发费用率由 5.12% 升至 5.69%），属良性上升。')""",
    """A(f'- **盈利能力**：毛利率稳定在 {min(quality[y]["gm"] for y in YEARS) * 100:.2f}%—'
  f'{max(quality[y]["gm"] for y in YEARS) * 100:.2f}% 区间；期间费用率总体呈下降趋势'
  f'（{quality["2023"]["exp_ratio"] * 100:.2f}% → {quality["2024"]["exp_ratio"] * 100:.2f}% → '
  f'{quality["2025"]["exp_ratio"] * 100:.2f}%），2026 年上半年小幅回升至 '
  f'{quality["2026H1"]["exp_ratio"] * 100:.2f}%，'
  '主因研发投入持续增加（研发费用率由 5.12% 升至 5.69%），费用管控整体有效。')""",
)

EDIT_CH7 = (
    """  f'约 **{multiple:.2f} 倍**（三年年化约 {irr * 100:.1f}%）。**回报空间有限，估值安全垫偏薄。**')
A()
A('## 八、风险提示与尽调缺口')""",
    """  f'约 **{multiple:.2f} 倍**（三年年化约 {irr * 100:.1f}%）。**回报空间有限，估值安全垫偏薄。**')
A('- **投资执行与交割条件**：① 完成上述尽调缺口的补充与书面结论确认；② 就客户集中度、专利诉讼'
  '未决事项取得管理层专项说明；③ 完成估值上限的商务谈判并落实于正式投资协议；④ 业绩承诺与'
  '回购条款经法务复核后签署。')
A('- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年'
  '承诺利润测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。')
A()
A('## 八、风险提示与尽调缺口')""",
)

EDIT_CH89 = (
    """A('**下一步动作**：就上述缺口补充尽调；与控股股东就估值上限、业绩承诺与回购条款进行谈判；'
  '条件成熟后提交投资决策委员会审议。')
A()
A('## 九、交易执行与投后安排')
A()
A('- **交割条件**：① 完成上述尽调缺口的补充与书面结论确认；② 就客户集中度、专利诉讼未决事项'
  '取得管理层专项说明；③ 完成估值上限的商务谈判并落实于正式投资协议；④ 业绩承诺与回购条款'
  '经法务复核后签署。')
A(f'- **投后监控指标**：按季度跟踪营业收入与扣非归母净利润（对照承诺值 {fm(promise["2026"])} / '
  f'{fm(promise["2027"])} 万元）、第一大客户收入占比、应收账款周转天数、经营活动现金流净额与'
  '净现比；任一指标出现显著不利偏离时，启动估值调整或退出程序。')
A('- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年'
  '承诺利润测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。')
A('- **信息披露与合规**：本次投资决策相关材料、测算过程与本备忘录一并归档，全部结论均可追溯到'
  '材料包中的原始文件或指引条款，确保决策依据可复核、可审计。')
A()""",
    """A('**下一步动作**：就上述缺口补充尽调；与控股股东就估值上限、业绩承诺与回购条款进行谈判；'
  '条件成熟后提交投资决策委员会审议。')
A()
A(f'**投后监控指标**：按季度跟踪营业收入与扣非归母净利润（对照承诺值 {fm(promise["2026"])} / '
  f'{fm(promise["2027"])} 万元）、第一大客户收入占比、应收账款周转天数、经营活动现金流净额与'
  '净现比；任一指标出现显著不利偏离时，启动估值调整或退出程序。')
A()
A('**信息披露与合规**：本次投资决策相关材料、测算过程与本备忘录一并归档，全部结论均可追溯到'
  '材料包中的原始文件或指引条款，确保决策依据可复核、可审计。')
A()""",
)

EDITS = [("第5条 期间费用率趋势", EDIT_PROFIT),
         ("第4条 第七章并入交割/退出", EDIT_CH7),
         ("第4条 第八章并入监控/披露 + 删第九章", EDIT_CH89)]

dry = "--dry-run" in sys.argv
for path in TARGETS:
    if not os.path.isfile(path):
        print(f"!! 缺文件: {path}")
        continue
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    original = text
    print("=" * 80)
    print(os.path.relpath(path, REPO))
    for label, (old, new) in EDITS:
        count = text.count(old)
        if count == 0:
            print(f"  [SKIP] {label}: 未匹配到（可能已修复）")
            continue
        text = text.replace(old, new)
        print(f"  [OK]   {label}: 替换 {count} 处")
    print(f"  第九章残留: {text.count('九、交易执行与投后安排')} 处")
    print(f"  '逐年上升'残留: {text.count('期间费用率逐年上升')} 处")
    if not dry and text != original:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("  已写入")
    elif dry:
        print("  （dry-run，未写入）")
