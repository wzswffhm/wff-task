# -*- coding: utf-8 -*-
"""检查控制组 job 的 F2P/P2P 终态，确认门禁：Oracle 全过、NOP 零 P2P 失败且至少一个 F2P 失败。"""
from __future__ import annotations

import json
import pathlib
import sys

BUILD = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wsparse-build\controls\jobs")


def main() -> int:
    for job in sorted(p for p in BUILD.iterdir() if p.is_dir()):
        trials = [d for d in job.iterdir() if d.is_dir() and "__" in d.name]
        if not trials:
            # Already-assembled layout: <job>/verifier/report.json
            trials = [job]
        for trial in trials:
            rp = trial / "verifier" / "report.json"
            if not rp.is_file():
                rp = trial / "verifier" / "result.json"
            if not rp.is_file():
                print(f"{job.name}: 无 verifier/report.json")
                continue
            doc = json.loads(rp.read_text(encoding="utf-8-sig"))
            cases = doc.get("cases") or []
            f2p = [c for c in cases if str(c.get("test_id", "")).startswith("f2p-")]
            p2p = [c for c in cases if str(c.get("test_id", "")).startswith("p2p-")]
            f2p_fail = [c["test_id"] for c in f2p if not c.get("passed")]
            p2p_fail = [c["test_id"] for c in p2p if not c.get("passed")]
            reward = (trial / "verifier" / "reward.txt")
            reward = reward.read_text(encoding="utf-8-sig").strip() if reward.is_file() else "?"
            print(f"{job.name:<16} reward={reward} validity={doc.get('run_validity')} "
                  f"score={doc.get('formal_score')} F2P fail={len(f2p_fail)}/{len(f2p)} "
                  f"P2P fail={len(p2p_fail)}/{len(p2p)}")
            if p2p_fail:
                print(f"    P2P 失败: {p2p_fail}")
            if not f2p_fail:
                print("    !! 没有任何 F2P 失败")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
