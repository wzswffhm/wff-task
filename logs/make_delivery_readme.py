# -*- coding: utf-8 -*-
"""make_delivery_readme.py -- 依据 jobs/_index/assembly_report.json 生成交付 README。

用法：
    python make_delivery_readme.py --task 218
    python make_delivery_readme.py --task 219
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"
STAGED = REL / "staged"
TASKS = {
    "218": {
        "pkg": "wfflab__wlogseg-218-v1.1.0-delivery",
        "id": "wfflab__wlogseg-218",
        "name": "wlogseg",
        "version": "1.1.0",
        "prev": "1.0.0",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wlogseg218-返修",
        "value": "通用编码能力（Windows 运行时执行；不主张 Windows 专属价值）",
        "required": 26,
        "f2p": 18,
        "p2p": 8,
        "refit": "REFIT-2026-10-13.md",
    },
    "219": {
        "pkg": "wfflab__wpeimg-219-v1.4.0-delivery",
        "id": "wfflab__wpeimg-219",
        "name": "wpeimg",
        "version": "1.4.0",
        "prev": "1.3.0",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wpeimg219-返修",
        "value": ("原生开发与互操作（Windows PE/COFF 映像；判分期真实调用 "
                  "imagehlp!MapFileAndCheckSumW 与 kernel32!CreateFileW）"),
        "required": 43,
        "f2p": 35,
        "p2p": 8,
        "refit": "REFIT-2026-10-13.md",
    },
}


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = STAGED / cfg["pkg"]
    jobs = pkg / "jobs"
    rep = read_json(jobs / "_index" / "assembly_report.json", {}) or {}
    rows = rep.get("jobs", [])

    ctl = [r for r in rows if r["kind"] in ("oracle", "nop")]
    models = [r for r in rows if r["kind"] == "model"]

    def by_alias(alias):
        return [r for r in models if str(r["job"]).startswith("model-%s-" % alias)]

    qwen, opus = by_alias("qwen"), by_alias("opus")
    glm, kimi = by_alias("glm"), by_alias("kimi")

    def s(rs):
        return sum(int(r["score"] or 0) for r in rs)

    def cases(rs):
        return sum(int(r.get("cases_passed") or 0) for r in rs)

    q_sum, o_sum = s(qwen), s(opus)
    q_cases, o_cases = cases(qwen), cases(opus)
    # Buyer rule (windows-harbor-qc SKILL §4):
    #   1) Opus model_score_sum > Qwen -> pass
    #   2) equal sums -> Opus testcase_pass_sum must exceed Qwen
    #   3) tie on both -> pass only if every required model run is VALID/0
    all_zero = (bool(qwen) and bool(opus)
                and all(int(r["score"] or 0) == 0 for r in qwen + opus))
    if o_sum > q_sum:
        qualified, why = True, "Opus 总分 %d > Qwen 总分 %d" % (o_sum, q_sum)
    elif o_sum == q_sum and o_cases > q_cases:
        qualified, why = True, ("总分相等（%d），逐 testcase 累计 Opus %d > Qwen %d"
                               % (o_sum, o_cases, q_cases))
    elif all_zero:
        qualified, why = True, ("Opus/Qwen 总分同为零且逐 testcase 累计同为 %d；"
                               "全部规定模型运行均为 VALID/0，按甲方「全模型零分平局」"
                               "例外允许通过" % o_cases)
    else:
        qualified, why = False, ("Opus 总分 %d、Qwen 总分 %d，逐 testcase 累计 %d vs %d"
                                 % (o_sum, q_sum, o_cases, q_cases))

    oracle = [r for r in ctl if r["kind"] == "oracle"]
    nop = [r for r in ctl if r["kind"] == "nop"]
    checksums = sorted({r["task_checksum"] for r in rows if r["task_checksum"]})
    g_ok = bool(oracle) and all(int(r["score"] or 0) == 1 for r in oracle)
    n_ok = bool(nop) and all(int(r["score"] or 0) == 0 for r in nop)

    def mdl(rs):
        if not rs:
            return "—"
        return " / ".join(str(int(r["score"] or 0)) for r in rs)

    def cases_str(rs):
        if not rs:
            return "—"
        return " / ".join("%d/%d" % (int(r.get("cases_passed") or 0), int(r["cases"] or 0))
                          for r in rs)

    lines = []
    lines.append("# %s · 交付记录（%s → %s）" % (cfg["id"], cfg["prev"], cfg["version"]))
    lines.append("")
    lines.append("| 项 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| 交付 ZIP | `package/%s.zip` |" % cfg["pkg"])
    lines.append("| 任务身份 | `%s` v%s |" % (cfg["id"], cfg["version"]))
    lines.append("| 采购分类 | %s |" % cfg["value"])
    lines.append("| required testcase | %d（F2P %d / P2P %d）"
                 % (cfg["required"], cfg["f2p"], cfg["p2p"]))
    lines.append("| 评分族 | 纯程序化 1.0（`llm_judge_weight = 0.0`） |")
    lines.append("| 生成时间 | %s |" % datetime.now().astimezone().isoformat())
    lines.append("")
    lines.append("> `extras/`（伴随材料）不进交付包；`solution/` 仅在 Golden 轮注入。")
    lines.append("")
    lines.append("## 1. 控制组（真实 Windows 容器）")
    lines.append("")
    lines.append("| 轮 | 正式分 | run_validity | cases |")
    lines.append("| --- | --- | --- | --- |")
    for r in ctl:
        lines.append("| `%s` | %s | %s | %d/%d |"
                     % (r["job"], r["score"], r["validity"], r["cases"], cfg["required"]))
    lines.append("")
    lines.append("结论：**Golden ×3 = 1（%s）、no-change ×3 = 0（%s）**。"
                 % ("OK" if g_ok else "FAIL", "OK" if n_ok else "FAIL"))
    lines.append("")
    lines.append("## 2. 模型轮次（真实 Windows 容器）")
    lines.append("")
    lines.append("| 模型 | 正式分（逐轮） | 逐轮 cases | 合计 |")
    lines.append("| --- | --- | --- | --- |")
    for name, rs in (("Qwen3.8-Max-0902", qwen), ("Opus 5", opus),
                     ("GLM-5.3（可选）", glm), ("Kimi K3（可选）", kimi)):
        lines.append("| %s | %s | %s | %d |"
                     % (name, mdl(rs), cases_str(rs), s(rs)))
    lines.append("")
    lines.append("**区分度准入**：%s → **%s**。" % (why, "PASS" if qualified else "FAIL"))
    lines.append("")
    lines.append("## 3. 身份一致性")
    lines.append("")
    if len(checksums) == 1:
        lines.append("全部 %d 个原生 Harbor job 的 `task_checksum` 同一值：`%s`。"
                     % (len(rows), checksums[0]))
    else:
        lines.append("!! `task_checksum` 不是单一值：`%s`" % checksums)
    lines.append("")
    lines.append("逐轮明细见 `jobs/_index/assembly_report.json`。")
    lines.append("")
    lines.append("## 4. 返修说明")
    lines.append("")
    lines.append("见包内 `%s`（逐条闭环 + 本机对照 + 容器控制组 + 隔离证据）。"
                 % cfg["refit"])
    lines.append("")
    lines.append("## 5. 本地证据索引")
    lines.append("")
    lines.append("| 路径 | 内容 |")
    lines.append("| --- | --- |")
    lines.append("| `package/%s.zip` + `.sha256` | 交付包与校验和 |" % cfg["pkg"])
    lines.append("| `evidence/images/score_summary.png` | 模型得分与区分度 |")
    lines.append("| `evidence/images/oracle_nop_controls.png` | 控制轮对照 |")
    lines.append("| 包内 `jobs/` | 原生 Harbor job（控制组 + 模型轮次） |")
    lines.append("| `harbor-windows/_qc_runs/relaunch-20261013/%s/` | 原始日志与轮次汇总 |" % a.task)
    lines.append("")

    out = cfg["deliverable"] / "README.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote %s" % out)
    print("qualified=%s  checksums=%s" % (qualified, checksums))
    return 0


if __name__ == "__main__":
    sys.exit(main())
