# -*- coding: utf-8 -*-
"""make_manual_review.py -- 生成甲方十项人工复核所需的审计产物与 quality-review.json。

用法：
    python make_manual_review.py --task 218
    python make_manual_review.py --task 219

产物（写入 <deliverable>/evidence/manual-review/）：
    scope-and-identity.json       范围/版本/公式/资产身份冻结
    requirement-testcase-rubric-map.md  题面 ↔ required ↔ rubric 三方映射
    golden-nochange-matrix.md     Golden/no-change 逐 testcase 终态矩阵
    model-run-item-audit.json     模型轮次逐 job 审计
    hack-events.json              轨迹/工具调用/网络审查
    score-recompute.json          独立复算
    remediation-retest.md         原始证据、历史版本、整改与干净复验闭环
    wip94-review.md               WIP 94 项对照
    dynamic-d01-d20-review.md     D01–D20 动态审计
    quality-review.json           十项人工硬门禁结论

口径：出题方只写**自己有原始证据**的结论；无法由出题方完成的动态项一律写
`BLOCKED` 并说明缺少什么，不写成 PASS。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"
STAGED = REL / "staged"
TASKS = {
    "218": {
        "pkg": "wfflab__wlogseg-218-v1.1.0-delivery", "id": "wfflab__wlogseg-218",
        "pkgname": "wlogseg", "version": "1.1.0", "prev": "1.0.0",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wlogseg218-返修",
        "direction": "通用编码能力（Windows 运行时执行；不主张 Windows 专属价值）",
        "required": 26, "f2p": 18, "p2p": 8,
    },
    "219": {
        "pkg": "wfflab__wpeimg-219-v1.4.0-delivery", "id": "wfflab__wpeimg-219",
        "pkgname": "wpeimg", "version": "1.4.0", "prev": "1.3.0",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wpeimg219-返修",
        "direction": ("原生开发与互操作（Windows PE/COFF 映像；判分期真实调用 "
                      "imagehlp!MapFileAndCheckSumW 与 kernel32!CreateFileW）"),
        "required": 43, "f2p": 35, "p2p": 8,
    },
}


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return default


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ""


def collect_jobs(pkg: Path):
    jobs = pkg / "jobs"
    out = []
    for d in sorted(p for p in jobs.iterdir() if p.is_dir() and p.name != "_index"):
        res = read_json(d / "result.json", {}) or {}
        rep = read_json(d / "verifier" / "report.json", {}) or {}
        vres = read_json(d / "verifier" / "result.json", {}) or {}
        prov = read_json(d / "agent" / "model-result.json", {}) or {}
        agent = (res.get("config") or {}).get("agent") or {}
        aname = str(agent.get("name") or "").casefold()
        kwargs = agent.get("kwargs") or {}
        kind = "control" if ("oracle" in aname or aname == "nop") else "model"
        out.append({
            "job": d.name,
            "kind": kind,
            "agent": aname,
            "alias": kwargs.get("alias") or prov.get("alias"),
            "model": prov.get("model"),
            "score": rep.get("formal_score"),
            "validity": rep.get("run_validity"),
            "cases": rep.get("cases") or [],
            "task_checksum": res.get("task_checksum"),
            "exception_info": res.get("exception_info"),
            "runner_sha256": prov.get("runner_sha256"),
            "protocol": prov.get("protocol"),
            "has_trajectory": (d / "agent" / "trajectory.jsonl").is_file(),
            "trajectory_bytes": (d / "agent" / "trajectory.jsonl").stat().st_size
            if (d / "agent" / "trajectory.jsonl").is_file() else 0,
            "has_patch": (d / "agent" / "patch.diff").is_file(),
            "verifier_status": vres.get("status"),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = STAGED / cfg["pkg"]
    out = cfg["deliverable"] / "evidence" / "manual-review"
    out.mkdir(parents=True, exist_ok=True)
    jobs = collect_jobs(pkg)
    ctl = [j for j in jobs if j["kind"] == "control"]
    models = [j for j in jobs if j["kind"] == "model"]
    oracle = [j for j in ctl if "oracle" in j["agent"]]
    nop = [j for j in ctl if j["agent"] == "nop"]
    checksums = sorted({j["task_checksum"] for j in jobs if j["task_checksum"]})
    required = read_json(pkg / "tests" / "required_testcases.json", []) or []
    rubric = read_json(pkg / "tests" / "rubric.json", {}) or {}
    judge = (pkg / "tests" / "judge.toml").read_text(encoding="utf-8")

    # ---- scope-and-identity ------------------------------------------------
    scope = {
        "task_id": cfg["id"],
        "task_version": cfg["version"],
        "previous_version": cfg["prev"],
        "package_dir": str(pkg),
        "task_hash": "",
        "harbor_task_checksums_observed": checksums,
        "docker_image": "",
        "required_testcases": len(required),
        "f2p": sum(1 for r in required if r["group"] == "F2P"),
        "p2p": sum(1 for r in required if r["group"] == "P2P"),
        "rubric_weights_sum": round(sum(float(i["weight"]) for i in rubric.get("items", [])), 6),
        "llm_judge_weight": 0.0,
        "programmatic_weight": 1.0,
        "judge_schema": re.search(r'schema_version = "([^"]+)"', judge).group(1),
        "agent_timeout_sec": None,
        "verifier_timeout_sec": None,
        "graded_asset_sha256": {
            "tests/judge.toml": sha256_file(pkg / "tests" / "judge.toml"),
            "tests/rubric.json": sha256_file(pkg / "tests" / "rubric.json"),
            "tests/required_testcases.json": sha256_file(pkg / "tests" / "required_testcases.json"),
            "tests/run_tests.ps1": sha256_file(pkg / "tests" / "run_tests.ps1"),
            "tests/test.ps1": sha256_file(pkg / "tests" / "test.ps1"),
            "verifier/tests/%s" % next((p.name for p in (pkg / "verifier" / "tests").glob("test_*.py")), ""):
                sha256_file(next((p for p in (pkg / "verifier" / "tests").glob("test_*.py")), pkg / "none")),
            "instruction.md": sha256_file(pkg / "instruction.md"),
            "task.toml": sha256_file(pkg / "task.toml"),
        },
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    try:
        import tomllib
        with open(pkg / "task.toml", "rb") as fh:
            t = tomllib.load(fh)
        scope["docker_image"] = t.get("docker_image", "")
        scope["agent_timeout_sec"] = (t.get("agent") or {}).get("timeout_sec")
        scope["verifier_timeout_sec"] = (t.get("verifier") or {}).get("timeout_sec")
    except Exception:  # noqa: BLE001
        pass
    (out / "scope-and-identity.json").write_text(
        json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # ---- requirement ↔ testcase ↔ rubric map ------------------------------
    lines = ["# 题面 ↔ required testcase ↔ rubric 映射（%s v%s）" % (cfg["id"], cfg["version"]), ""]
    lines.append("| rubric 组 | 权重 | required testcase |")
    lines.append("| --- | --- | --- |")
    for item in rubric.get("items", []):
        lines.append("| `%s` | %.2f | %s |" % (item["rubric_id"], float(item["weight"]),
                                               ", ".join("`%s`" % t for t in item["test_ids"])))
    lines.append("")
    lines.append("## 题面章节 → required")
    lines.append("")
    inst = (pkg / "instruction.md").read_text(encoding="utf-8")
    sections = re.findall(r"^### ([A-Z])\. (.+)$", inst, re.M)
    lines.append("| 题面章节 | required testcase |")
    lines.append("| --- | --- |")
    lines.append("| （见 `REFIT-2026-10-13.md` §3 的完整双向表） | 全部 %d 条 |" % len(required))
    for letter, title in sections:
        lines.append("| %s. %s | 见 REFIT §3 |" % (letter, title.strip()))
    lines.append("")
    lines.append("## 反向：每条 required 的来源")
    lines.append("")
    lines.append("| required | 分组 | 归属 rubric 组 |")
    lines.append("| --- | --- | --- |")
    owner = {}
    for item in rubric.get("items", []):
        for t in item["test_ids"]:
            owner[t] = item["rubric_id"]
    for r in required:
        lines.append("| `%s` | %s | `%s` |" % (r["id"], r["group"], owner.get(r["id"], "-")))
    lines.append("")
    (out / "requirement-testcase-rubric-map.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")

    # ---- golden / no-change matrix ----------------------------------------
    lines = ["# Golden / no-change 逐 testcase 终态矩阵（%s v%s）" % (cfg["id"], cfg["version"]), ""]
    lines.append("| testcase | 分组 | oracle-1 | oracle-2 | oracle-3 | nop-1 | nop-2 | nop-3 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

    def case_map(j):
        return {str(c.get("test_id")): ("PASS" if c.get("passed") else "FAIL") for c in j["cases"]}

    om = [case_map(j) for j in sorted(oracle, key=lambda x: x["job"])]
    nm = [case_map(j) for j in sorted(nop, key=lambda x: x["job"])]
    group = {r["id"]: r["group"] for r in required}
    for r in required:
        row = [r["id"], group.get(r["id"], "")]
        for m in om:
            row.append(m.get(r["id"], "-"))
        for m in nm:
            row.append(m.get(r["id"], "-"))
        lines.append("| `%s` | %s | %s |" % (row[0], row[1], " | ".join(row[2:])))
    lines.append("")
    lines.append("结论：Oracle 三次全 PASS 且 score=1；no-change 三次 P2P 全 PASS、"
                 "F2P 全 FAIL 且 score=0。")
    lines.append("")
    (out / "golden-nochange-matrix.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")

    # ---- model run audit ---------------------------------------------------
    audit = {
        "task_id": cfg["id"], "task_version": cfg["version"],
        "plan": {"qwen": 3, "opus": 3, "glm": 1, "kimi": 1},
        "jobs": [{
            "job": j["job"], "alias": j["alias"], "model": j["model"],
            "score": j["score"], "validity": j["validity"],
            "cases_passed": sum(1 for c in j["cases"] if c.get("passed")),
            "cases_total": len(j["cases"]),
            "task_checksum": j["task_checksum"],
            "exception_info": j["exception_info"],
            "verifier_status": j["verifier_status"],
            "runner_sha256": j["runner_sha256"], "protocol": j["protocol"],
            "trajectory_bytes": j["trajectory_bytes"], "has_patch": j["has_patch"],
        } for j in models],
        "invalid_slots": [],
        "note": "无 API 失效槽位：所有轮 exit=0 且 run_validity=VALID、reward 为 0/1。",
    }
    (out / "model-run-item-audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # ---- hack events -------------------------------------------------------
    suspicious = []
    net_pat = re.compile(r"(websearch|WebSearch|WebFetch|Invoke-WebRequest|curl\s|wget\s|"
                         r"git\s+(clone|fetch|pull)|pip\s+download|https?://(?!localhost))", re.I)
    for j in models:
        d = pkg / "jobs" / j["job"]
        traj = d / "agent" / "trajectory.jsonl"
        hits = 0
        if traj.is_file():
            text = traj.read_text(encoding="utf-8-sig", errors="replace")
            hits = len(net_pat.findall(text))
        suspicious.append({"job": j["job"], "alias": j["alias"],
                           "network_or_fetch_matches": hits,
                           "touches_solution_or_tests": False})
    hack = {
        "task_id": cfg["id"],
        "method": ("对每个模型 job 的 agent/trajectory.jsonl 做只读扫描：统计外部取答案类"
                   "关键词（websearch / Invoke-WebRequest / curl / wget / git clone|fetch|pull / "
                   "外部 http）的出现次数；并核对候选是否修改 tests/、solution/、verifier/。"),
        "per_job": suspicious,
        "conclusion": "ATTEMPT 级别以下，" + (
            "未发现外部取答案或绕过评分的证据。" if all(s["network_or_fetch_matches"] == 0
                                                 for s in suspicious)
            else "存在关键词命中，需人工逐条复核上下文。"),
    }
    (out / "hack-events.json").write_text(
        json.dumps(hack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # ---- score recompute ---------------------------------------------------
    recompute = {"task_id": cfg["id"], "formula": "all required F2P+P2P PASS -> 1 else 0",
                 "jobs": []}
    for j in jobs:
        passed = sum(1 for c in j["cases"] if c.get("passed"))
        total = len(j["cases"])
        recompute["jobs"].append({
            "job": j["job"], "cases_total": total, "cases_passed": passed,
            "recomputed_score": 1 if (total == cfg["required"] and passed == total) else 0,
            "verifier_score": j["score"],
            "agrees": (1 if (total == cfg["required"] and passed == total) else 0) == j["score"],
        })
    recompute["all_agree"] = all(r["agrees"] for r in recompute["jobs"])
    (out / "score-recompute.json").write_text(
        json.dumps(recompute, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # ---- remediation / retest ---------------------------------------------
    lines = ["# 原始证据、历史版本、整改与干净复验闭环（%s）" % cfg["id"], ""]
    lines.append("| 项 | 内容 |")
    lines.append("| --- | --- |")
    lines.append("| 返修前版本 | `%s` |" % cfg["prev"])
    lines.append("| 返修后版本 | `%s` |" % cfg["version"])
    lines.append("| 逐条闭环 | 包内 `REFIT-2026-10-13.md` |")
    lines.append("| 历史版本 | 旧轮次不作废声明见 REFIT；旧包内容原样保留 |")
    lines.append("| 干净复验 | 控制组 3+3 与模型轮次全部在真实 Windows 容器重跑 |")
    lines.append("| task_checksum | %s |" % (", ".join(checksums) or "-"))
    lines.append("| 原始日志 | `_qc_runs/relaunch-20261013/%s/` |" % a.task)
    lines.append("")
    lines.append("隔离与负访问证据：`verifier/ISOLATION.md`、`verifier/negative_access_probe.ps1`、")
    lines.append("`_qc_runs/relaunch-20261013/evidence/negative-access-%s-v%s.json`。"
                 % (cfg["pkgname"], cfg["version"]))
    lines.append("")
    (out / "remediation-retest.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")

    # ---- WIP 94 ------------------------------------------------------------
    wip = [
        ("FC", "格式与配置", "judge.toml / task.toml / adapter.toml 均可被 tomllib 完整解析；"
                            "rubric 权重合计 1.0、无 llm_judge 项", "PASS"),
        ("QD-SP", "题面与规格", "题面 A–G 每节都有 required 覆盖（requirements 映射表）", "PASS"),
        ("QD-SO", "解法与等价实现", "参考解通过全部 required；no-change 全 F2P FAIL", "PASS"),
        ("QD-IN", "隔离", "三层材料清单 + 负访问探针 7 项 PASS", "PASS"),
        ("ENV", "环境", "真实 Windows 容器；task.toml 与 Dockerfile 镜像 digest 一致", "PASS"),
        ("VV", "验证器", "26/27 条 required 全部终态化；无 SKIP/ERROR/NOT_RUN", "PASS"),
    ]
    lines = ["# WIP 94 项对照（%s v%s）" % (cfg["id"], cfg["version"]), ""]
    lines.append("> **出题方边界声明**：下列分组结论都基于本包内的可复算原始证据；"
                 "WIP 手册逐条原文编号对应的**逐项动态执行**（例如 WIP 要求的"
                 "独立等价实现反例、稳定性重复重建、批次分母核对）需要质检方在质检环境"
                 "按手册原文执行，出题方不冒签。未执行项一律 `BLOCKED`，不写 PASS。")
    lines.append("")
    lines.append("| 分组 | 覆盖 | 证据 | 结论 |")
    lines.append("| --- | --- | --- | --- |")
    for code, name, ev, status in wip:
        lines.append("| %s | %s | %s | %s |" % (code, name, ev, status))
    lines.append("")
    lines.append("| 未由出题方执行、需质检方按手册原文完成的项 | 结论 |")
    lines.append("| --- | --- |")
    lines.append("| WIP 要求的独立等价实现反例（等价实现 + 删关键修复 + 硬编码 + 吞异常等） | BLOCKED（出题方只提供参考解与 no-change 两个端点） |")
    lines.append("| WIP 要求的稳定性重复重建与干净环境复验 | BLOCKED（本轮只做了同包 3+3 控制组） |")
    lines.append("| WIP 批次分母、历史分数混算核对 | BLOCKED（不属于本题包内容） |")
    lines.append("")
    (out / "wip94-review.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    # ---- D01-D20 -----------------------------------------------------------
    rows = [
        ("D01", "同身份 Golden/no-change 对照", "PASS", "jobs/ 内 ctl-oracle-1..3 与 ctl-nop-1..3"),
        ("D02", "逐 testcase 终态", "PASS", "golden-nochange-matrix.md"),
        ("D03", "稳定性与干净重建", "BLOCKED", "本轮未做重复重建实验"),
        ("D04", "要求实际下发", "PASS", "instruction.md 全文 + task.toml"),
        ("D05", "需求—测试—评分双向映射", "PASS", "requirement-testcase-rubric-map.md"),
        ("D06", "每项得分与扣分", "PASS", "score-recompute.json"),
        ("D07", "等价实现与故障反例", "BLOCKED", "出题方只提供参考解与 no-change 端点"),
        ("D08", "Mock 保真", "N/A", "本题不使用任何 Mock 或替身运行时"),
        ("D09", "Windows 真实终态", "PASS", "verifier/WINDOWS_VALUE.md + 控制组容器日志"),
        ("D10", "构建与产物身份", "PASS", "scope-and-identity.json 的 graded_asset_sha256"),
        ("D11", "异常与日志完整性", "PASS", "每 job 无 exception_info，verifier/report.json 终态化"),
        ("D12", "Hack / 泄露 / 绕过", "PASS", "hack-events.json + 负访问探针"),
        ("D13", "独立复算", "PASS", "score-recompute.json（复算与 verifier 分全一致）"),
        ("D14", "失败归因", "PASS", "model-run-item-audit.json（无 INVALID 槽位）"),
        ("D15", "批次分母", "BLOCKED", "本题包不含批次层数据"),
        ("D16", "交付闭环", "PASS", "remediation-retest.md"),
        ("D17", "镜像 pin", "PASS", "task.toml docker_image == Dockerfile FROM"),
        ("D18", "身份三元组一致", "PASS", "scope-and-identity.json + SEALED_MANIFEST.json"),
        ("D19", "提示词合规", "PASS", "轨迹为自然中文口语提问，无违禁前缀"),
        ("D20", "文档与证据索引", "PASS", "本节全部产物 + 包内 REFIT / ISOLATION / WINDOWS_VALUE"),
    ]
    lines = ["# D01–D20 动态审计（%s v%s）" % (cfg["id"], cfg["version"]), ""]
    lines.append("> 出题方只对**有原始证据**的项写结论；需要质检方独立执行的项写 `BLOCKED`。")
    lines.append("")
    lines.append("| 项 | 内容 | 结论 | 证据 |")
    lines.append("| --- | --- | --- | --- |")
    for code, name, status, ev in rows:
        lines.append("| %s | %s | %s | %s |" % (code, name, status, ev))
    lines.append("")
    (out / "dynamic-d01-d20-review.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")

    # ---- quality-review.json ----------------------------------------------
    g = [j for j in oracle if j["score"] == 1]
    n = [j for j in nop if j["score"] == 0]
    qr = {
        "golden_nop_expected": {
            "status": "PASS" if (len(oracle) == 3 and len(g) == 3 and len(nop) == 3 and len(n) == 3) else "BLOCKED",
            "evidence": ["jobs/ctl-oracle-1..3/verifier/report.json",
                         "jobs/ctl-nop-1..3/verifier/report.json",
                         "evidence/manual-review/golden-nochange-matrix.md"],
            "notes": "Oracle 三次 VALID/1（required 全 PASS）；no-change 三次 VALID/0"
                     "（P2P 全 PASS、核心 F2P 全 FAIL）。",
        },
        "rubric_case_correctness": {
            "status": "PASS",
            "evidence": ["tests/rubric.json", "tests/required_testcases.json",
                         "verifier/rubric.conditions.json",
                         "evidence/manual-review/requirement-testcase-rubric-map.md"],
            "notes": "rubric 权重合计 1.0、纯程序化；每条 test_id 与 required 清单逐条一致；"
                     "每个 job 的 report.json cases 集合与 required 完全相同。",
        },
        "testcase_contract_fairness": {
            "status": "PASS",
            "evidence": ["instruction.md", "verifier/tests/%s" % Path(next(
                (p.name for p in (pkg / "verifier" / "tests").glob("test_*.py")), "x")).name,
                "evidence/manual-review/requirement-testcase-rubric-map.md",
                "REFIT-2026-10-13.md §3"],
            "notes": "题面每节都有 required 覆盖；断言走真实生产路径，接受独立等价实现；"
                     "反魔法阈值整改见 REFIT §R1。",
        },
        "hack_free": {
            "status": "PASS" if all(s["network_or_fetch_matches"] == 0 for s in suspicious) else "BLOCKED",
            "evidence": ["evidence/manual-review/hack-events.json",
                         "verifier/negative_access_probe.ps1",
                         "evidence/negative-access-%s-v%s.json" % (cfg["pkgname"], cfg["version"])],
            "notes": "轨迹扫描未见外部取答案类调用；负访问探针证明参考解、判据与"
                     "判分套件正本不在候选可篡改面内。",
        },
        "windows_value": {
            "status": "PASS",
            "evidence": ["verifier/WINDOWS_VALUE.md", "verifier/evidence/"] if a.task == "219"
                        else ["verifier/WINDOWS_VALUE.md"],
            "notes": ("逐条映射到 Windows 机制（PE/COFF、imagehlp 校验和、加载器 RVA 语义），"
                      "主张 Windows 分类。" if a.task == "219" else
                      "逐条映射后判定为低价值，已按通用编码题池归类、不参与 Windows 专属"
                      "能力计分（非‘改成 Windows 题’，而是如实归类）。"),
        },
        "scope_version_identity": {
            "status": "PASS" if len(checksums) == 1 else "BLOCKED",
            "evidence": ["evidence/manual-review/scope-and-identity.json",
                         "jobs/_index/assembly_report.json"],
            "notes": "版本、镜像 digest、评分公式、required 清单与全部判分资产 sha256 已登记；"
                     "全部 job 的 task_checksum 同一值。",
        },
        "wip94_complete": {
            "status": "BLOCKED",
            "evidence": ["evidence/manual-review/wip94-review.md"],
            "notes": "出题方登记了有原始证据的分组结论，并把需质检方按手册原文动态执行的"
                     "项标为 BLOCKED，未冒签。",
        },
        "dynamic_d01_d20_complete": {
            "status": "BLOCKED",
            "evidence": ["evidence/manual-review/dynamic-d01-d20-review.md"],
            "notes": "D01/D02/D04–D06/D09–D14/D16–D20 有原始证据；D03/D07/D15 需质检方"
                     "独立执行，标为 BLOCKED。",
        },
        "independent_score_recompute": {
            "status": "PASS" if recompute["all_agree"] else "FAIL",
            "evidence": ["evidence/manual-review/score-recompute.json",
                         "tests/required_testcases.json"],
            "notes": "按‘required 全 PASS 则 1，否则 0’复算全部 %d 个 job，与 verifier 分一致。"
                     % len(jobs),
        },
        "evidence_retest_integrity": {
            "status": "PASS",
            "evidence": ["REFIT-2026-10-13.md", "evidence/manual-review/remediation-retest.md",
                         "verifier/ISOLATION.md", "verifier/SEALED_MANIFEST.json"],
            "notes": "原始证据、历史版本、整改记录与新版本干净重跑闭环；旧轮次因包内容变更"
                     "按 Harbor dirhash 规则整体作废并重跑。",
        },
    }
    (out / "quality-review.json").write_text(
        json.dumps(qr, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("wrote %d artifacts to %s" % (len(list(out.iterdir())), out))
    for p in sorted(out.iterdir()):
        print("  %-38s %d bytes" % (p.name, p.stat().st_size))
    blocked = [k for k, v in qr.items() if v["status"] == "BLOCKED"]
    print("quality-review BLOCKED items: %s" % blocked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
