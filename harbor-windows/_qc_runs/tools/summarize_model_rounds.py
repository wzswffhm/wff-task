"""Summarize a model's candidate rounds for a task from the runner's runs/ store.

Reports every VALID round in chronological order (no cherry-picking) plus the
累加 score, and separately lists rounds excluded because the agent itself failed
(HTTP error / timeout / no_tool_call) —那些不计入难度统计，但必须如实列出。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RUNNER = Path(r"C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-04_outside-harbor-win\runner")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--model", default="QWEN")
    ap.add_argument("--runs-root", default=str(RUNNER / "runs"))
    args = ap.parse_args()

    root = Path(args.runs_root) / args.task
    if not root.is_dir():
        print(f"no runs for {args.task}")
        return 1

    valid, excluded, other = [], [], []
    for job in sorted(p for p in root.iterdir() if p.is_dir()):
        for res in job.rglob("result.json"):
            try:
                d = json.loads(res.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError):
                continue
            model = str(d.get("model") or "").upper()
            if d.get("mode") != "candidate" or (args.model and model != args.model):
                continue
            rec = {
                "job": job.name,
                "verdict": d.get("verdict"),
                "status": d.get("report_status"),
                "agent_status": d.get("agent_status"),
                "turns": d.get("turns"),
                "reason": str(d.get("reason") or "")[:90],
                "mtime": d.get("mtime_utc"),
            }
            if rec["status"] != "VALID":
                other.append(rec)
            elif str(rec["agent_status"] or "completed") not in ("completed", ""):
                excluded.append(rec)
            else:
                valid.append(rec)

    valid.sort(key=lambda r: (r["mtime"] or "", r["job"]))
    print(f"=== {args.task} / {args.model} : VALID candidate rounds = {len(valid)}")
    for i, r in enumerate(valid, 1):
        print(f"  {i}. {r['job']}  verdict={r['verdict']}  turns={r['turns']}  {r['reason'][:60]}")
    print(f"  score_sum = {sum(int(r['verdict'] or 0) for r in valid)}  (满分 {len(valid)})")
    if excluded:
        print(f"  -- 排除（agent 自身失败，不计入）: {len(excluded)}")
        for r in excluded:
            print(f"     {r['job']}  agent_status={r['agent_status']}  turns={r['turns']}")
    if other:
        print(f"  -- 非 VALID: {len(other)}")
        for r in other:
            print(f"     {r['job']}  status={r['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
