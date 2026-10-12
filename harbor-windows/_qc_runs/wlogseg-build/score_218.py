# -*- coding: utf-8 -*-
"""score_218.py —— 汇总 wfflab__wlogseg-218 的四模型跑分并算区分度准入。

不对模型发起任何调用，只读题包 extras/model_runs 下已回填的 report.json /
per_testcase.json；输出到 _qc_runs/wlogseg-build/evidence/。

用法：
    python score_218.py [--package <题包目录>] [--out <evidence 目录>]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import date

ROOT = r"C:\Users\Administrator\Desktop\wff-task"
DEFAULT_PKG = os.path.join(ROOT, "harbor-windows", "wfflab__wlogseg-218-v1.0.0-delivery")
DEFAULT_OUT = os.path.join(ROOT, "harbor-windows", "_qc_runs", "wlogseg-build", "evidence")

# key → (显示名, 目录名, 要求轮数, 角色)
MODELS = [
    ("qwen3.8-max", "Qwen3.8-Max-0902", "qwen3.8-max-0902", 3, "primary"),
    ("opus-5", "Opus 5 @ 4router.net", "opus-5", 3, "primary"),
    ("glm-5.3", "GLM-5.3", "glm-5.3", 1, "auxiliary"),
    ("kimi-k3", "Kimi K3", "kimi-k3", 1, "auxiliary"),
]


def read_json(path, default=None):
    try:
        with io.open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except Exception:
        return default


def collect(pkg):
    runs_root = os.path.join(pkg, "extras", "model_runs")
    out = {}
    for key, label, mdir, need, role in MODELS:
        d = os.path.join(runs_root, mdir)
        rec = {"key": key, "label": label, "dir": mdir, "required": need, "role": role,
               "runs": [], "valid": 0, "invalid": 0, "pending": 0,
               "score_sum": 0, "pass_sum": 0, "scores": []}
        for n in range(1, 10):
            rd = os.path.join(d, "run-%d" % n)
            meta_p = os.path.join(rd, "meta.json")
            if not os.path.isfile(meta_p):
                continue
            meta = read_json(meta_p, {}) or {}
            rep = read_json(os.path.join(rd, "report.json"), {}) or {}
            pt = read_json(os.path.join(rd, "per_testcase.json"), {}) or {}
            status = meta.get("status")
            score = rep.get("score")
            results = pt.get("results") or {}
            passed = sum(1 for v in results.values() if str(v).upper() == "PASS")
            item = {"run": n, "status": status, "score": score,
                    "invalid_reason": meta.get("invalid_reason"),
                    "agent_status": (rep.get("judge") or {}).get("run_validity"),
                    "elapsed_sec": meta.get("elapsed_sec"),
                    "steps": meta.get("steps"),
                    "output_tokens": meta.get("output_tokens"),
                    "patch_bytes": meta.get("patch_bytes"),
                    "passed": passed, "total": len(results),
                    "f2p_all_pass": pt.get("f2p_all_pass"),
                    "p2p_all_pass": pt.get("p2p_all_pass")}
            rec["runs"].append(item)
            if status == "VALID":
                rec["valid"] += 1
                rec["scores"].append(score)
                if isinstance(score, (int, float)):
                    rec["score_sum"] += score
                rec["pass_sum"] += passed
            elif status == "INVALID":
                rec["invalid"] += 1
            else:
                rec["pending"] += 1
        rec["scores_known"] = (len(rec["scores"]) == rec["required"]
                               and all(isinstance(s, (int, float)) for s in rec["scores"]))
        rec["validity"] = ("READY" if rec["valid"] >= rec["required"] and rec["invalid"] == 0
                           else ("RETEST_REQUIRED" if rec["invalid"] else "PENDING"))
        out[key] = rec
    return out


def admission(models):
    q, o = models["qwen3.8-max"], models["opus-5"]
    adm = {"condition": None, "passed": None, "reason": None, "blocking": []}
    if q["valid"] < 3 or o["valid"] < 3:
        adm["reason"] = "主模型有效运行不足 3 次，暂不可判定"
        adm["blocking"].append("insufficient_valid_runs")
    elif q["validity"] != "READY" or o["validity"] != "READY":
        adm["reason"] = "存在 INVALID 运行未补跑"
        adm["blocking"].append("invalid_runs_not_retested")
    elif not (q["scores_known"] and o["scores_known"]):
        adm["reason"] = "3 次响应均有效，但正式分尚未全部回填"
        adm["blocking"].append("scores_not_filled")
    else:
        qs, os_ = q["score_sum"], o["score_sum"]
        if os_ > qs:
            adm.update(condition=1, passed=True,
                       reason="Opus5.model_score_sum(%s) > Qwen.model_score_sum(%s)" % (os_, qs))
        elif qs == 0 and os_ == 0:
            if o["pass_sum"] > q["pass_sum"]:
                adm.update(condition=2, passed=True,
                           reason="双 0 场景，Opus5.testcase_pass_sum(%s) > Qwen(%s)"
                                  % (o["pass_sum"], q["pass_sum"]))
            else:
                adm.update(condition=2, passed=False,
                           reason="双 0 且 testcase 表现无严格区分（Opus %s vs Qwen %s）"
                                  % (o["pass_sum"], q["pass_sum"]))
        else:
            adm.update(passed=False,
                       reason="两者正式分和相同且不全为 0（Opus %s vs Qwen %s）" % (os_, qs))
    for key in ("glm-5.3", "kimi-k3"):
        if models[key]["valid"] < 1:
            adm.setdefault("blocking_aux", []).append("%s 无有效运行" % key)
    return adm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", default=DEFAULT_PKG)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()

    pkg = os.path.abspath(a.package)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)

    models = collect(pkg)
    tid = "wfflab__wlogseg-218"
    adm = admission(models)

    summary = {"task_id": tid, "generated_at": date.today().isoformat(),
               "package": pkg, "models": models, "admission": adm}
    with io.open(os.path.join(out, "model_validation_summary_218.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    with io.open(os.path.join(out, "model_summary_218.csv"), "w",
                 encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh)
        w.writerow(["task_id", "model", "model_dir", "role", "runs_required", "runs_valid",
                    "runs_invalid", "runs_pending", "model_score_sum", "testcase_pass_sum",
                    "scores", "validity"])
        for key, _, _, _, _ in MODELS:
            m = models[key]
            w.writerow([tid, m["label"], m["dir"], m["role"], m["required"], m["valid"],
                        m["invalid"], m["pending"], m["score_sum"], m["pass_sum"],
                        "/".join("-" if s is None else str(s) for s in m["scores"]),
                        m["validity"]])

    verdict = "PASS" if adm["passed"] else ("BLOCKED" if adm["passed"] is None else "FAIL")
    md = ["# wfflab__wlogseg-218 多模型验证与区分度报告", "",
          "生成时间：%s" % summary["generated_at"], "",
          "题包：`%s`" % pkg, "",
          "## 1. 区分度准入", "",
          "| Qwen score_sum | Opus score_sum | Qwen pass_sum | Opus pass_sum | 条件 | 结论 |",
          "|---|---|---|---|---|---|",
          "| %s | %s | %s | %s | %s | **%s** — %s |" % (
              models["qwen3.8-max"]["score_sum"], models["opus-5"]["score_sum"],
              models["qwen3.8-max"]["pass_sum"], models["opus-5"]["pass_sum"],
              adm["condition"] or "-", verdict, adm["reason"]), "",
          "## 2. 逐模型逐轮明细", "",
          "| 模型 | run | agent 状态 | 正式分 | 逐项 PASS | F2P 全过 | P2P 全过 | 步数 | 输出 tokens | 补丁字节 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for key, label, _, _, _ in MODELS:
        for r in models[key]["runs"]:
            md.append("| %s | run-%d | %s | %s | %s/%s | %s | %s | %s | %s | %s |" % (
                label, r["run"], r["status"], "-" if r["score"] is None else r["score"],
                r["passed"], r["total"], r["f2p_all_pass"], r["p2p_all_pass"],
                r["steps"], r["output_tokens"], r["patch_bytes"]))
    md += ["", "## 3. 准入规则", "", "```",
           "条件 1: Opus5.model_score_sum > Qwen.model_score_sum",
           "条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum",
           "```", "",
           "> 只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。",
           "> Opus 5 走 4router.net，必须流式（skill ref 08 §7.14）；非流式在长输出下会撞传输层超时。", ""]
    with io.open(os.path.join(out, "model_validation_report_218.md"), "w",
                 encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md))

    for key, label, _, _, _ in MODELS:
        m = models[key]
        print("%-22s valid=%d/%d invalid=%d pending=%d score_sum=%s pass_sum=%s %s"
              % (label, m["valid"], m["required"], m["invalid"], m["pending"],
                 m["score_sum"], m["pass_sum"], m["validity"]))
        for r in m["runs"]:
            print("    run-%d status=%-8s score=%-5s pass=%s/%s f2p=%s p2p=%s steps=%s out=%s"
                  % (r["run"], r["status"], r["score"], r["passed"], r["total"],
                     r["f2p_all_pass"], r["p2p_all_pass"], r["steps"], r["output_tokens"]))
    print("\n准入：%s — %s" % (verdict, adm["reason"]))
    if adm.get("blocking"):
        print("blocking: %s" % ", ".join(adm["blocking"]))
    if adm.get("blocking_aux"):
        print("blocking_aux: %s" % ", ".join(adm["blocking_aux"]))
    print("报告目录：%s" % out)
    return 0 if adm["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
