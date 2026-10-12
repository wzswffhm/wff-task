# -*- coding: utf-8 -*-
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = pathlib.Path(__file__).resolve().parents[1] / "evidence" / "fix6_extract" / \
    "work_fin-b01_20261006_fix6-150" / "FIN3-WKN-150" / "跑分产物与轨迹"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

for ex in EXECUTORS:
    data = json.loads((BASE / ex / "reward-details.json").read_text(encoding="utf-8"))
    reward = data["reward"]
    by_id = {c["id"]: c for c in reward["criteria"]}
    crit = by_id["R27"]
    print(f"=== {ex} reward={reward['score']} R27={crit['value']} raw={crit['raw']}")
    print(crit.get("reasoning", ""))
    print()
    zero = [c["id"] for c in reward["criteria"] if float(c["value"]) == 0]
    partial = [(c["id"], c["value"]) for c in reward["criteria"] if 0 < float(c["value"]) < 1]
    print("zero:", ",".join(zero))
    print("partial:", partial)
    print()
