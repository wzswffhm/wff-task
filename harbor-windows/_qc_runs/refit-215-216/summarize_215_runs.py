#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 215 的跑分结果摘要（Markdown + JSON），供 git 提交信息与飞书说明引用。

无论收尾流程成功与否都会先生成这份摘要，保证结果被如实记录。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

WS = r"C:\Users\Administrator\Desktop\wff-task"
HW = os.path.join(WS, "harbor-windows")
PKG = os.path.join(HW, "wfflab__wfmt-215-v2.1.0-delivery")
RUNS = os.path.join(WS, r"deliverables\2026-10-04_outside-harbor-win\runner\runs\wfflab__wfmt-215")
OUT_DIR = os.path.join(HW, r"_qc_runs\refit-215-216")
MD = os.path.join(OUT_DIR, "215-run-summary.md")
JS = os.path.join(OUT_DIR, "215-run-summary.json")

LABELS = [
    ("no-change", "NOP 控制（no-change）", "control"),
    ("golden", "Oracle 控制（golden）", "control"),
    ("opus-5", "Opus 5", "model"),
    ("qwen3.8-max-0902", "Qwen3.8-Max-0902", "model"),
    ("glm-5.3", "GLM-5.3（新规则下可选）", "optional"),
    ("kimi-k3", "Kimi K3（新规则下可选）", "optional"),
]


def hhmm(iso):
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%m-%d %H:%M:%S")
    except ValueError:
        return str(iso)


runs: dict[str, list[dict]] = {}
invalid: dict[str, list[dict]] = {}
pending: list[dict] = []

for run_id in sorted(os.listdir(RUNS)) if os.path.isdir(RUNS) else []:
    rp = os.path.join(RUNS, run_id)
    if not os.path.isdir(rp) or run_id.startswith("_"):
        continue
    for label in sorted(os.listdir(rp)):
        lp = os.path.join(rp, label)
        if not os.path.isdir(lp):
            continue
        rj = os.path.join(lp, "result.json")
        item = {"run_id": run_id, "label": label}
        if not os.path.isfile(rj):
            item["idle_min"] = round((datetime.now().timestamp() - os.path.getmtime(lp)) / 60.0, 1)
            pending.append(item)
            continue
        try:
            doc = json.load(open(rj, encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            item["error"] = str(exc)
            invalid.setdefault(label, []).append(item)
            continue
        item.update({
            "verdict": doc.get("verdict"),
            "validity": doc.get("run_validity"),
            "passed": doc.get("passed"),
            "total": doc.get("total"),
            "duration": doc.get("duration_seconds"),
            "finished": (doc.get("runner") or {}).get("finished_at"),
            "formal_score": doc.get("formal_score"),
        })
        (runs if item["validity"] == "VALID" else invalid).setdefault(label, []).append(item)

lines = []
lines.append("# wfflab__wfmt-215 跑分结果摘要")
lines.append("")
lines.append("- 题包版本：**2.1.1**（目录名 `wfflab__wfmt-215-v2.1.0-delivery`）")
lines.append("- 生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
lines.append("- 模型口径：甲方 2026-10-13 规则 —— GLM/Kimi **不再必需**，只跑 控制组 + Opus + Qwen（12 轮）")
lines.append("- 运行环境：本地 Outside-Harbor runner + Windows 容器（`outside-harbor/wfflab__wfmt-215:2.1.1`）")
lines.append("")
lines.append("## 逐轮明细")
lines.append("")

summary = {}
for label, disp, kind in LABELS:
    got = sorted(runs.get(label, []), key=lambda x: x["run_id"])
    if not got:
        continue
    lines.append("### %s（%d 轮）" % (disp, len(got)))
    lines.append("")
    lines.append("| run_id | verdict | testcase | 有效性 | 耗时 | 结束 |")
    lines.append("|---|---|---|---|---|---|")
    for r in got:
        lines.append("| `%s` | %s | %s/%s | %s | %ss | %s |" % (
            r["run_id"], r["verdict"], r["passed"], r["total"], r["validity"],
            r["duration"], hhmm(r["finished"])))
    lines.append("")
    scores = [r["verdict"] for r in got]
    passes = [r["passed"] or 0 for r in got]
    summary[label] = {
        "display": disp, "kind": kind, "n_valid": len(got),
        "verdicts": scores,
        "model_score_sum": sum(int(s or 0) for s in scores),
        "testcase_pass_sum": sum(passes),
        "testcase_detail": ["%s/%s" % (r["passed"], r["total"]) for r in got],
        "durations": [r["duration"] for r in got],
    }

if invalid:
    lines.append("## 无效轮次（不计入能力判定）")
    lines.append("")
    for label, items in invalid.items():
        for it in items:
            lines.append("- `%s` / `%s`：validity=%s" % (it["run_id"], label, it.get("validity")))
    lines.append("")

if pending:
    lines.append("## 检查时仍在运行的轮次")
    lines.append("")
    for it in pending:
        lines.append("- `%s` / `%s`：已 %s 分钟无更新" % (it["run_id"], it["label"], it.get("idle_min")))
    lines.append("")

# 结论
lines.append("## 结论")
lines.append("")
concl = []
ctl = {k: v for k, v in summary.items() if v["kind"] == "control"}
mod = {k: v for k, v in summary.items() if v["kind"] == "model"}
opt = {k: v for k, v in summary.items() if v["kind"] == "optional"}

for label, v in ctl.items():
    ok = all(int(s or 0) == (1 if label == "golden" else 0) for s in v["verdicts"]) and v["n_valid"] == 3
    concl.append("- 控制组 `%s`：%s，%s" % (label, v["verdicts"],
               "符合预期（%s）" % ("全 1" if label == "golden" else "全 0") if ok else "**偏离预期**"))

if "opus-5" in mod and "qwen3.8-max-0902" in mod:
    o = mod["opus-5"]["model_score_sum"]
    q = mod["qwen3.8-max-0902"]["model_score_sum"]
    op = mod["opus-5"]["testcase_pass_sum"]
    qp = mod["qwen3.8-max-0902"]["testcase_pass_sum"]
    concl.append("- 模型累计分：Opus 5 = **%d**，Qwen3.8-Max = **%d**" % (o, q))
    concl.append("- testcase 累计通过数：Opus = **%d**，Qwen = **%d**" % (op, qp))
    if o > q:
        concl.append("- 区分度门禁：**通过**（Opus 总分严格高于 Qwen）")
    elif o == q:
        if op > qp:
            concl.append("- 区分度门禁：**通过**（总分相等，Opus 的 testcase 累计通过数严格更多）")
        else:
            all_scores = [int(s or 0) for v in mod.values() for s in v["verdicts"] if s is not None]
            if all_scores and all(x == 0 for x in all_scores):
                concl.append("- 区分度门禁：**通过（全模型有效零分例外）**——全部规定模型运行均为 VALID/0，"
                             "零分平局不因区分度单独返修")
            else:
                concl.append("- 区分度门禁：**未通过**（总分相等且 testcase 累计未拉开，且不满足全零例外）")
    else:
        concl.append("- 区分度门禁：**未通过**（Opus 总分低于 Qwen）")

for label, v in opt.items():
    concl.append("- 可选模型 `%s`：%s（新规则下不参与必需判定）" % (label, v["verdicts"]))

for c in concl:
    lines.append(c)
lines.append("")

text = "\n".join(lines)
os.makedirs(OUT_DIR, exist_ok=True)
open(MD, "w", encoding="utf-8", newline="\n").write(text)
json.dump({"generated_at": datetime.now().isoformat(), "package_version": "2.1.1",
           "summary": summary, "invalid": {k: [i["run_id"] for i in v] for k, v in invalid.items()},
           "pending": [i["run_id"] for i in pending],
           "conclusions": concl},
          open(JS, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)

print("跑分摘要已生成：")
print("  %s" % MD)
print("  %s" % JS)
print()
print(text)
sys.exit(0)
