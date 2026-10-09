#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 tests/rubrics.toml 生成设计态 rubrics.json（v1 同结构）。"""
from __future__ import annotations

import json
import os
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.join(HERE, "..", "FIN3-WKN-152")

DIM = {
    "R01": "指令遵循", "R02": "指令遵循",
    "R03": "内容质量-结论正确性", "R04": "内容质量-结论正确性",
    "R06": "内容质量-结论正确性",
    "R05": "内容质量-数值与计算准确性", "R07": "内容质量-数值与计算准确性",
    "R08": "内容质量-数值与计算准确性", "R10": "内容质量-数值与计算准确性",
    "R11": "内容质量-数值与计算准确性", "R16": "内容质量-数值与计算准确性",
    "R17": "内容质量-数值与计算准确性", "R20": "内容质量-数值与计算准确性",
    "R23": "内容质量-数值与计算准确性", "R28": "内容质量-数值与计算准确性",
    "R09": "内容质量-专业规范", "R13": "内容质量-专业规范",
    "R14": "内容质量-专业规范", "R26": "内容质量-专业规范",
    "R27": "内容质量-专业规范",
    "R12": "内容质量-事实忠实性", "R15": "内容质量-事实忠实性",
    "R19": "内容质量-事实忠实性", "R25": "内容质量-事实忠实性",
    "R29": "内容质量-事实忠实性",
    "R18": "内容质量-分析与论证质量", "R21": "内容质量-分析与论证质量",
    "R22": "内容质量-分析与论证质量",
    "R30": "内容质量-数值与计算准确性", "R31": "内容质量-数值与计算准确性",
    "R32": "内容质量-数值与计算准确性", "R33": "内容质量-专业规范",
    "R24": "操作与交付安全",
    "N01": "内容质量-事实忠实性", "N02": "内容质量-专业规范",
    "N03": "安全合规", "N04": "操作与交付安全",
}
SUBJECTIVE = {"R18", "R22"}

COMMENT = (
    "原始评分细则（设计态）。id 与 tests/rubrics.toml 的 criterion 一一对应，便于人工追溯。"
    "type 在本文件用设计态取值 binary/gradient；gradient 条目的 levels 键必须为比例键 "
    "1/0.75/0.5/0.25/0（1=完全满足、0=完全不满足；与判官侧整数 5/4/3/2/1 按 (judge-1)/4 一一对应），"
    "落到 tests/rubrics.toml 时写为 likert + points = 5 并把每一档锚点写进 description。"
    "weight 设计态取值 {+10,+7,+5,+4,-7,-5}，落到 tests/rubrics.toml 时负分改写为 negate = true + 正 weight。"
    "任务为 weakness 类（v2.0.0，复杂度 C5），覆盖 W02-关键冲突下自行选边 / 修改输入、"
    "W04-多要求/多交付物下缺少 Requirement Coverage Accounting、"
    "W07-长表格/多 Sheet 下的数据覆盖与抗干扰能力弱、W11-无据自造数据与口径、W12-跨源交叉核对缺失。"
)


def main():
    src = os.path.join(TASK_DIR, "tests", "rubrics.toml")
    d = tomllib.load(open(src, "rb"))
    crit = d["criterion"]

    items = []
    for c in crit:
        cid = c["id"]
        neg = bool(c.get("negate"))
        item = {
            "id": cid,
            "description": c["description"],
            "dimension": DIM[cid],
            "criterion_type": "Subjective" if cid in SUBJECTIVE else "Objective",
            "criterion_necessity": "Explicit",
            "type": c["type"],
            "weight": float(c["weight"]),
            "levels": None,
        }
        if neg:
            item["negate"] = True
        items.append(item)

    pos = [x for x in items if not x.get("negate")]
    neg = [x for x in items if x.get("negate")]
    s_max = sum(x["weight"] for x in pos)
    cq_pos = sum(x["weight"] for x in pos if x["dimension"].startswith("内容质量-"))
    share = round(cq_pos / s_max, 3)

    out = {
        "_comment": COMMENT,
        "task_id": "FIN3-WKN-152",
        "deliverables_inspected": [
            "output/FIN3-WKN-152_ipo_model.xlsx",
            "output/FIN3-WKN-152_pricing_memo.md",
            "output/FIN3-WKN-152_reproduce.py",
            "output/FIN3-WKN-152_qoe_bridge.csv",
            "output/FIN3-WKN-152_valuation_matrix.csv",
            "output/FIN3-WKN-152_source_trace.csv",
            "output/FIN3-WKN-152_charts.png",
        ],
        "items": items,
        "metadata": {
            "scoring": {
                "s_max": float(s_max),
                "pooling": "reward = clip((sum(pos_w*v) - sum(neg_w*(1-v))) / s_max, 0, 1)",
            },
            "criteria_count": len(items),
            "critically_important_ids": [x["id"] for x in pos if x["weight"] >= 10.0],
        },
        "_distribution_check": {
            "critically_important_ge_2": len([x for x in pos if x["weight"] >= 10.0]) >= 2,
            "content_quality_positive_share": share,
            "content_quality_positive_share_ge_30pct": share >= 0.30,
            "always_required_dimensions_present": sorted({
                "指令遵循", "内容质量-结论正确性",
                "内容质量-分析与论证质量", "内容质量-事实忠实性"} &
                {x["dimension"] for x in items}),
            "no_negative_weight_in_tests_rubrics_toml":
                "N01–N04 落到 tests/rubrics.toml 时改写为 negate = true + 正 weight",
        },
    }

    dst = os.path.join(TASK_DIR, "rubrics.json")
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"[OK] rubrics.json: {len(items)} items, S_max={s_max}, "
          f"pos={len(pos)}, neg={len(neg)}, cq_share={share}")


if __name__ == "__main__":
    main()
