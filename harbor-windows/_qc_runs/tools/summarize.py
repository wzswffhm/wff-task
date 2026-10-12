"""Summarize a qc_full.py evidence directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8"))
    for task_id, entry in data["tasks"].items():
        print("=" * 78)
        print(task_id, "gate:", json.dumps(entry.get("gate"), ensure_ascii=False))
        for run in entry["runs"]:
            cases = [c for fr in run["formal_results"] for c in fr.get("cases", [])]
            f2p = [c for c in cases if c["group"] == "F2P"]
            p2p = [c for c in cases if c["group"] == "P2P"]
            scores = [x.get("score") for x in run["formal_results"]]
            print(f"  {run['agent']:6s} try{run['attempt']} status={run['status']:8s} "
                  f"score={scores} exit={run['exit_code']} "
                  f"F2P_pass={sum(c['status'] == 'PASS' for c in f2p)}/{len(f2p)} "
                  f"P2P_pass={sum(c['status'] == 'PASS' for c in p2p)}/{len(p2p)}")
            if run["agent"] == "nop" and run["attempt"] == 1:
                print("     nop F2P FAIL:", [c["id"] for c in f2p if c["status"] == "FAIL"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
