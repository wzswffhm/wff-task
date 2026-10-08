"""Audit each job's agent/ and verifier/ payload against the platform spec:
    agent/    -> Agent 轨迹、轮次输入输出、工具调用
    verifier/ -> testcase 结果、正式分数、日志和运行
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_ap = argparse.ArgumentParser()
_ap.add_argument("--task", default="wfflab__wreparse-217")
_args = _ap.parse_args()

TASK = _args.task
JOBS = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows") / TASK / "jobs"

TOOL_HINTS = re.compile(r"tool_call|tool_use|run_command|write_file|read_file|function|toolResult|tool_result", re.I)
TURN_HINTS = re.compile(r'"turn"|turn_index|step|round|assistant|user', re.I)

rows = []
for job in sorted(p for p in JOBS.iterdir() if p.is_dir()):
    if not (job / "job.json").is_file():
        continue
    doc = json.loads((job / "job.json").read_text(encoding="utf-8-sig"))
    agent_files = sorted(f.name for f in (job / "agent").iterdir()) if (job / "agent").is_dir() else []
    verifier_files = sorted(f.name for f in (job / "verifier").iterdir()) if (job / "verifier").is_dir() else []

    traj = ""
    traj_name = ""
    for cand in ("agent.log", "oracle.txt"):
        p = job / "agent" / cand
        if p.is_file():
            traj = p.read_text(encoding="utf-8", errors="ignore")
            traj_name = cand
            break
    rows.append({
        "job": job.name,
        "mode": doc.get("mode"),
        "model": doc.get("model_key"),
        "verdict": doc.get("verdict"),
        "status": doc.get("report_status"),
        "turns_field": doc.get("turns"),
        "agent_files": agent_files,
        "verifier_files": verifier_files,
        "traj_name": traj_name,
        "traj_bytes": len(traj.encode("utf-8")),
        "traj_lines": traj.count("\n") + 1 if traj else 0,
        "has_tool": bool(TOOL_HINTS.search(traj)),
        "has_turn": bool(TURN_HINTS.search(traj)),
    })

print(f"{'job':<46} {'mode':<10} {'model':<7} {'turns':>5} {'agent/':<26} traj")
print("-" * 130)
for r in rows:
    print(f"{r['job']:<46} {str(r['mode']):<10} {str(r['model']):<7} {str(r['turns_field']):>5} "
          f"{','.join(r['agent_files'])[:25]:<26} {r['traj_name']} {r['traj_bytes']}B "
          f"tools={'Y' if r['has_tool'] else 'n'} turns={'Y' if r['has_turn'] else 'n'}")

print()
print("=== verifier 侧覆盖 ===")
from collections import Counter
c = Counter()
for r in rows:
    for f in r["verifier_files"]:
        c[f] += 1
for k, v in c.most_common():
    print(f"  {k:<20} {v}/{len(rows)}")

print()
print("=== 缺口 ===")
for r in rows:
    gaps = []
    if not r["traj_name"]:
        # A control round legitimately has no trajectory; it must say so instead.
        if "README.md" not in r["agent_files"]:
            gaps.append("无 agent 轨迹文件且无声明")
    if not any(f in r["verifier_files"] for f in ("checks.json", "report.json")):
        gaps.append("无 testcase 结果")
    if "result.json" not in r["verifier_files"]:
        gaps.append("无正式分数")
    if not any(f in r["verifier_files"] for f in ("test.log", "test-stdout.txt", "stderr.log", "trial.log")):
        gaps.append("无日志")
    if r["turns_field"] is None and r["mode"] == "candidate":
        gaps.append("turns=null")
    if gaps:
        print(f"  {r['job']}: {', '.join(gaps)}")
