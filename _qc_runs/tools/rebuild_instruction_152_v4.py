# -*- coding: utf-8 -*-
"""152 题面（v4）改造：为新判据补公平性要求，同时严守红线——不写任何答案数值、无引导性注释。

只写"格式/口径/呈现方式"（模型必须知道才公平），答案锚点（-118.361、31.27、60 个文件…）一律不写。
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
INS = TASK / "instruction.md"

raw = INS.read_text(encoding="utf-8")
edits = []


def rep(old, new, label):
    global raw
    n = raw.count(old)
    if n != 1:
        print(f"  [!!] {label}: 匹配 {n} 次（应为 1）")
        edits.append((label, False))
        return
    raw = raw.replace(old, new, 1)
    print(f"  [OK] {label}")
    edits.append((label, True))


print("=" * 96)
print("题面改造")
print("=" * 96)

# 1) 敏感性矩阵：给出网格（格式要求，非答案）
rep(
    "20. **敏感性分析**：给出 2024E 增长率 × EV/Revenue 倍数的每股价值敏感性矩阵（至少 5×5）。",
    "20. **敏感性分析**：给出 2024E 增长率 × EV/Revenue 倍数的每股价值敏感性矩阵，\n"
    "    **增长率轴取 18% / 20% / 22% / 24% / 26%，倍数轴取 4.0x / 4.3x / 4.5x / 4.8x / 5.0x**\n"
    "    （5×5 共 25 格，每格给出单点数值、不得留空或以区间代替），并标注 base case。",
    "L83 敏感性矩阵给定网格",
)

# 2) xlsx 新增 Tieout_Detail 勾稽明细表（结构化增量交付）
rep(
    "须至少包含 `Inputs`、`QoE`、`Valuation`、`Sensitivity`、`Offering_Proceeds`、`Dilution`、`Pricing_Summary`、`Error_Audit`、`Source_Trace` 九个可辨识的工作表（措辞可微调，但须能一一对应上述九个模块），各表填写实质内容并给出计算过程或取值来源；其中 `Error_Audit` 须覆盖数据核验中发现的**全部**明细异常",
    "须至少包含 `Inputs`、`QoE`、`Valuation`、`Sensitivity`、`Offering_Proceeds`、`Dilution`、`Pricing_Summary`、`Error_Audit`、`Source_Trace`、`Tieout_Detail` 十个可辨识的工作表（措辞可微调，但须能一一对应上述十个模块），各表填写实质内容并给出计算过程或取值来源；其中 `Error_Audit` 须覆盖数据核验中发现的**全部**明细异常，`Tieout_Detail` 为勾稽明细表，**逐行列出**每一项序列的明细加总值、目标年度数、差额、异常类型与处置结果（至少覆盖月度收入、分部收入、地区收入、SBC 明细合计与 cap table 合计等全部勾稽项）",
    "L98 xlsx 增补 Tieout_Detail 表",
)

# 3) 备忘录：数据核验段要求分条（对应 R33）
rep(
    "备忘录须含一个**数据核验**段落，逐条列出核验发现的明细异常、判定依据与处置结果",
    "备忘录须含一个**数据核验**段落，**一行一条**列出核验发现的明细异常（不得把多条异常合并成一段叙述），每条给出文件、行或月份、现象、判定依据与处置结果",
    "L99 备忘录核验段分条",
)

# 4) 新增 26–29 条工作成果要求
rep(
    "25. **材料完整性**：不得修改、删除 `input_files` 中的任何文件，也不得在其中新增文件。\n",
    "25. **材料完整性**：不得修改、删除 `input_files` 中的任何文件，也不得在其中新增文件。\n"
    "26. **材料清点**：交付物中须清点 `/app/input_files/` 下的文件总数与来源目录数，\n"
    "    并**按目录分别列出每个目录的文件数**（分项之和须与总数勾稽），不得只给总数。\n"
    "27. **计算过程呈现**：关键结论（盈利质量调整、2024E 分母、净现金桥、每股价值推导链、\n"
    "    费用扣减、股本桥、各处勾稽差额）**必须逐行写出计算算式并带列报数值**，\n"
    "    不得只给出最终结果数，也不得把多个计算步骤合并成一句叙述。\n"
    "28. **分列不合并**：凡存在多个组成部分的项目（现金与有价证券、承销费与固定费用、\n"
    "    primary / secondary / greenshoe、各类明细异常、各类旧底稿错误、各项约束条件）\n"
    "    **必须分行分列给出**；合计数不得替代分项，同类项不得归并成一行。\n"
    "29. **方法论理由**：对所有关键方法论选择（估值倍数取值方式、被排除的竞争数据来源、\n"
    "    适用的政策版本、费用计提基数等）**须显式写出选择理由**；仅给出数值结论而未说明\n"
    "    理由的，视为该项未完成。\n",
    "L90 后新增 26–29 条",
)

# 5) 检查：题面不得出现判据里的答案锚点
print()
print("=" * 96)
print("红线自检：题面不得出现答案锚点 / 引导性注释")
print("=" * 96)
ANSWERS = ["-118.361", "118.361", "980.915", "1,213.122", "1213.122",
           "31.27", "34.26", "37.25", "519.402", "486.432", "158.993090",
           "162.293090", "106.590", "666.701", "804.029 ×", "57.100",
           "60 个文件", "60 个", "25.970", "2.479", "15.247", "68.979",
           "66.500", "49.086", "401.176", "811.946"]
hit = [a for a in ANSWERS if a in raw]
print(f"  答案锚点命中: {hit if hit else '无 ✓'}")

HINT = ["注意：", "提示：", "小心", "别忘了", "这里有个", "易错", "常见错误",
        "正确答案", "参考答案", "标准答案", "rubric", "判官", "评分标准", "golden"]
hh = [h for h in HINT if h.lower() in raw.lower()]
print(f"  引导性注释命中: {hh if hh else '无 ✓'}")

# 判据钦定的网格是否已进题面（公平性）
for k in ["18% / 20% / 22% / 24% / 26%", "4.0x / 4.3x / 4.5x / 4.8x / 5.0x",
          "Tieout_Detail", "逐行写出计算算式", "按目录分别列出", "显式写出选择理由"]:
    print(f"  公平性要求「{k}」: {'✓ 已在题面' if k in raw else '✗ 缺失'}")

print()
ok = all(f for _, f in edits) and not hit and not hh
if ok and raw != INS.read_text(encoding="utf-8"):
    INS.write_text(raw, encoding="utf-8", newline="\n")
    print(f"[写出] {INS}  {len(raw.splitlines())} 行  {len(raw.encode('utf-8')):,} B")
elif not ok:
    print("[!!] 存在问题，未写入")
print()
print(">>> " + ("题面改造完成" if ok else "需人工处理"))
