# -*- coding: utf-8 -*-
"""汇总 219 各模型轮次与 Oracle/NOP 控制轮，输出分数与 testcase 通过数对比。

用法：
    python summarize_wpeimg_rounds.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

BUILD = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wpeimg-build")
MODEL_JOBS = BUILD / "model-rounds" / "jobs"
CONTROL_JOBS = BUILD / "qc-controls1" / "jobs"
REQUIRED = (BUILD.parent.parent / "wfflab__wpeimg-219-v1.0.0-delivery"
            / "tests" / "required_testcases.json")
ORDER = ["qwen", "opus", "glm", "kimi"]


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def alias_of(job_name: str) -> str:
    for name in ORDER + ["oracle", "nop"]:
        if job_name.endswith("-" + name) or ("-%s-" % name) in job_name:
            return name
    return job_name


def collect(root: Path) -> list[dict]:
    rows: list[dict] = []
    if not root.is_dir():
        return rows
    for job_dir in sorted(root.iterdir()):
        if not job_dir.is_dir():
            continue
        for trial in sorted(job_dir.iterdir()):
            if not trial.is_dir():
                continue
            reward = trial / "verifier" / "reward.txt"
            if not reward.is_file():
                continue
            report = read_json(trial / "verifier" / "report.json", {}) or {}
            cases = {}
            for case in report.get("cases") or []:
                tid = case.get("test_id")
                if tid:
                    cases[tid] = "PASS" if case.get("passed") else "FAIL"
            rows.append({
                "job": job_dir.name,
                "alias": alias_of(job_dir.name),
                "trial": trial.name,
                "score": reward.read_text(encoding="utf-8-sig").strip(),
                "validity": report.get("run_validity"),
                "passed": report.get("passed"),
                "total": report.get("total"),
                "cases": cases,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="把汇总写成 JSON")
    args = ap.parse_args()

    required = read_json(REQUIRED, []) or []
    required_ids = [r["id"] for r in required if isinstance(r, dict) and r.get("id")]
    groups = {r["id"]: r.get("group") for r in required if isinstance(r, dict)}

    model_rows = collect(MODEL_JOBS)
    control_rows = collect(CONTROL_JOBS)

    print("== 控制轮（Oracle / NOP）==")
    for row in control_rows:
        print("  %-34s score=%-3s validity=%-6s passed=%s/%s"
              % (row["job"], row["score"], row["validity"], row["passed"], row["total"]))

    print("\n== 模型轮 ==")
    print("  %-8s %-4s %-6s %-8s %-9s %s"
          % ("模型", "轮", "score", "validity", "testcase", "F2P 通过"))
    stats: dict[str, dict] = {}
    for row in model_rows:
        f2p = [t for t in required_ids if groups.get(t) == "F2P"]
        f2p_pass = sum(1 for t in f2p if row["cases"].get(t) == "PASS")
        print("  %-8s #%-3s %-6s %-8s %-9s %d/%d"
              % (row["alias"], row["job"].rsplit("-", 1)[-1], row["score"],
                 row["validity"], "%s/%s" % (row["passed"], row["total"]),
                 f2p_pass, len(f2p)))
        bucket = stats.setdefault(row["alias"], {"runs": 0, "score_sum": 0,
                                                 "pass_sum": 0, "failed_cases": {}})
        bucket["runs"] += 1
        if row["score"] in ("0", "1"):
            bucket["score_sum"] += int(row["score"])
        bucket["pass_sum"] += int(row["passed"] or 0)
        for tid in required_ids:
            if row["cases"].get(tid) != "PASS":
                bucket["failed_cases"][tid] = bucket["failed_cases"].get(tid, 0) + 1

    print("\n== 汇总对比（按 testcase 通过数）==")
    print("  %-8s %-6s %-10s %-12s %s" % ("模型", "轮数", "score 和", "testcase 和", "未通过的 testcase"))
    for name in sorted(stats, key=lambda k: -stats[k]["pass_sum"]):
        b = stats[name]
        failed = ", ".join("%s x%d" % (k, v) for k, v in
                           sorted(b["failed_cases"].items(), key=lambda kv: -kv[1])) or "-"
        print("  %-8s %-6d %-10d %-12d %s"
              % (name, b["runs"], b["score_sum"], b["pass_sum"], failed))

    if args.json:
        Path(args.json).write_text(
            json.dumps({"model": model_rows, "control": control_rows, "stats": stats},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("\n已写出 %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
