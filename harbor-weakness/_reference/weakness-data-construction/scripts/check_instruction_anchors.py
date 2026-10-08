# -*- coding: utf-8 -*-
"""改写题面后，核对所有判据锚点字符串仍逐字存在于 instruction.md。"""
import os
import sys

ROOT = (r"C:\Users\Administrator\Documents\Codex\2026-09-29\new-chat-2\outputs"
        r"\zq-金融-投资研究-20260929")

ANCHORS = {
    "FIN-127-W": [
        "FIN-127_神州数码研究分析报告.docx",
        "FIN-127_关键财务与估值数据表.xlsx",
        "FIN-127_关键事件核验表.xlsx",
        "关键财务指标", "分部口径对照", "分部毛利率", "盈利预测与估值", "单季推导",
        "01-神州数码-2025年年度报告.pdf", "03-神州数码-2026年半年度报告.pdf",
        "14-投资研究部内部备忘-跟踪要点.docx",
        "一、公司概况", "二、行业分析", "三、公司业务分析", "四、财务分析", "五、盈利预测",
        "六、估值分析", "七、股价预测", "八、投资建议与风险提示", "九、关键事件核验",
        "十、分部口径可比性调整表", "十一、单季数据推导",
        "3500 字", "6500 字", "/app/output/", "/app/input_files/",
    ],
    "FIN-128-W": [
        "FIN-128_瑞茂通尽职调查报告.docx",
        "FIN-128_瑞茂通财务与负债数据表.xlsx",
        "FIN-128_瑞茂通股权质押明细表.xlsx",
        "主要财务数据", "应收账款账龄", "刚性负债构成", "受限资产", "涉诉客户", "质押到期分布",
        "14-投资研究部内部备忘-尽调跟踪要点.docx",
        "3500 字", "/app/output/", "/app/input_files/",
    ],
    "FIN-129-W": [
        "FIN-129_菏泽城投控股集团有限公司信用尽职调查报告.docx",
        "FIN-129_区域财政与债务指标表.xlsx",
        "FIN-129_公司关键指标与债务结构表.xlsx",
        "区域财政与债务指标", "关键指标跨期对照",
        "/app/output/", "/app/input_files/",
    ],
}


def main():
    bad = 0
    for task, anchors in ANCHORS.items():
        path = os.path.join(ROOT, task, "instruction.md")
        text = open(path, encoding="utf-8").read()
        miss = [a for a in anchors if a not in text]
        print(f"{task}: 锚点 {len(anchors)} 个, 缺失 {len(miss)}")
        for m in miss:
            print("   MISSING:", m)
        bad += len(miss)
    print("总缺失:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
