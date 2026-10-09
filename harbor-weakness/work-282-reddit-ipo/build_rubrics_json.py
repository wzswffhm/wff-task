#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 tests/rubrics.toml 生成设计态 rubrics.json，保证 description/weight 零漂移。"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path("harbor-weakness/FIN3-WKN-152")
TOML = ROOT / "tests/rubrics.toml"
OUT = ROOT / "rubrics.json"

# id -> (dimension, criterion_type)
DIM = {
    "R01": ("指令遵循", "Objective"),
    "R02": ("指令遵循", "Objective"),
    "R03": ("内容质量-结论正确性", "Objective"),
    "R04": ("内容质量-结论正确性", "Objective"),
    "R05": ("内容质量-数值与计算准确性", "Objective"),
    "R06": ("内容质量-数值与计算准确性", "Objective"),
    "R07": ("内容质量-数值与计算准确性", "Objective"),
    "R08": ("内容质量-数值与计算准确性", "Objective"),
    "R09": ("内容质量-数值与计算准确性", "Objective"),
    "R10": ("内容质量-数值与计算准确性", "Objective"),
    "R11": ("内容质量-数值与计算准确性", "Objective"),
    "R12": ("内容质量-专业规范", "Objective"),
    "R13": ("内容质量-专业规范", "Objective"),
    "R14": ("内容质量-专业规范", "Objective"),
    "R15": ("内容质量-专业规范", "Objective"),
    "R16": ("内容质量-专业规范", "Objective"),
    "R17": ("内容质量-专业规范", "Objective"),
    "R18": ("内容质量-事实忠实性", "Objective"),
    "R19": ("内容质量-事实忠实性", "Objective"),
    "R20": ("内容质量-分析与论证质量", "Subjective"),
    "R21": ("内容质量-事实忠实性", "Objective"),
    "R22": ("操作与交付安全", "Objective"),
    "R23": ("安全合规", "Objective"),
    "R24": ("超预期贡献", "Subjective"),
    "N01": ("内容质量-事实忠实性", "Objective"),
    "N02": ("内容质量-专业规范", "Objective"),
    "N03": ("内容质量-专业规范", "Objective"),
}

DELIVERABLES = [
    "output/FIN3-WKN-152_ipo_model.xlsx",
    "output/FIN3-WKN-152_pricing_memo.md",
    "output/FIN3-WKN-152_reproduce.py",
]

COMMENT = (
    "原始评分细则（设计态）。id 与 tests/rubrics.toml 的 criterion 一一对应，便于人工追溯。"
    "type 在本文件用设计态取值 binary/gradient；gradient 条目的 levels 键必须为比例键 "
    "1/0.75/0.5/0.25/0（1=完全满足、0=完全不满足；与判官侧整数 5/4/3/2/1 按 (judge-1)/4 一一对应），"
    "落到 tests/rubrics.toml 时写为 likert + points = 5 并把每一档锚点写进 description。"
    "weight 设计态取值 {+10,+7,+3,-10,-7}，落到 tests/rubrics.toml 时负分改写为 negate = true + 正 weight。"
    "任务为 weakness 类，覆盖 W02-关键冲突下自行选边、W07-长表格/多 Sheet 下的数据覆盖与抗干扰能力弱、"
    "W12-跨源交叉核对缺失。"
)


def parse_levels(desc: str) -> dict | None:
    """从 description 的「评分锚点：5=…；4=…」提取比例键 levels。"""
    if "评分锚点：" not in desc:
        return None
    tail = desc.split("评分锚点：", 1)[1]
    levels = {}
    for seg in re.split(r"；", tail):
        seg = seg.split(" Deliverables to inspect:")[0].strip().rstrip("。")
        m = re.match(r"^([1-5])\s*=\s*(.+)$", seg)
        if m:
            judge_i = int(m.group(1))
            ratio = {5: "1", 4: "0.75", 3: "0.5", 2: "0.25", 1: "0"}[judge_i]
            levels[ratio] = m.group(2).strip()
    order = ["1", "0.75", "0.5", "0.25", "0"]
    if sorted(levels, key=order.index) != order or len(levels) != 5:
        raise SystemExit(f"锚点提取不完整: {levels}")
    return levels


def main() -> int:
    raw = TOML.read_bytes().decode("utf-8")
    data = tomllib.loads(raw)
    crit = data["criterion"]

    items = []
    for c in crit:
        dim, ctype = DIM[c["id"]]
        negate = bool(c.get("negate"))
        design_type = "gradient" if c["type"] == "likert" else "binary"
        w = -float(c["weight"]) if negate else float(c["weight"])
        levels = parse_levels(c["description"]) if design_type == "gradient" else None
        item = {
            "id": c["id"],
            "description": c["description"],
            "dimension": dim,
            "criterion_type": ctype,
            "criterion_necessity": "Explicit",
            "type": design_type,
            "weight": w,
            "levels": levels,
        }
        if negate:
            item["negate"] = True
        items.append(item)

    pos = [x for x in items if not x.get("negate")]
    neg = [x for x in items if x.get("negate")]
    s_max = sum(x["weight"] for x in pos)
    crit_ids = [x["id"] for x in pos if x["weight"] == 10.0]

    content_ids = {f"R{i:02d}" for i in range(3, 22)}
    cq = sum(x["weight"] for x in pos if x["id"] in content_ids)
    share = round(cq / s_max, 4)

    always = ["指令遵循", "内容质量-结论正确性", "内容质量-分析与论证质量",
              "内容质量-事实忠实性"]
    dims = {x["dimension"] for x in items}

    doc = {
        "_comment": COMMENT,
        "task_id": "FIN3-WKN-152",
        "deliverables_inspected": DELIVERABLES,
        "items": items,
        "metadata": {
            "scoring": {
                "s_max": s_max,
                "pooling": "reward = clip((sum(pos_w*v) - sum(neg_w*(1-v))) / s_max, 0, 1)",
            },
            "criteria_count": len(items),
            "critically_important_ids": crit_ids,
        },
        "_distribution_check": {
            "critically_important_ge_2": len(crit_ids) >= 2,
            "content_quality_positive_share": share,
            "content_quality_positive_share_ge_30pct": share >= 0.30,
            "always_required_dimensions_present": [d for d in always if d in dims],
            "no_negative_weight_in_tests_rubrics_toml":
                "N01–N03 落到 tests/rubrics.toml 时改写为 negate = true + 正 weight",
        },
    }

    # ---------- 与 toml 零漂移校验 ----------
    t_ids = [c["id"] for c in crit]
    j_ids = [x["id"] for x in items]
    assert t_ids == j_ids, f"id 集合不一致: {set(t_ids) ^ set(j_ids)}"
    for tc, jc in zip(crit, items):
        assert tc["description"] == jc["description"], f"description 漂移: {tc['id']}"
        tw = -float(tc["weight"]) if tc.get("negate") else float(tc["weight"])
        assert abs(tw - jc["weight"]) < 1e-9, f"weight 漂移: {tc['id']}"
        assert bool(tc.get("negate")) == bool(jc.get("negate")), f"negate 漂移: {tc['id']}"
    t_pos = sum(float(c["weight"]) for c in crit if not c.get("negate"))
    assert abs(t_pos - s_max) < 1e-9, f"S_max 不一致: toml={t_pos} json={s_max}"

    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")

    print(f"生成 {OUT}")
    print(f"  条数={len(items)}  正向={len(pos)}  负向={len(neg)}")
    print(f"  S_max = {s_max}  (toml 正向和 = {t_pos})  一致 ✓")
    print(f"  Critically Important = {crit_ids}")
    print(f"  内容质量正分占比 = {share:.4f}")
    print(f"  always_required 覆盖 = {doc['_distribution_check']['always_required_dimensions_present']}")
    print(f"  description/weight/negate 零漂移校验 ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
