# -*- coding: utf-8 -*-
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
REJ = ROOT / "harbor-weakness" / "FIN3-WKN-150" / "_rejudge"
ARCH = ROOT / "harbor-weakness" / "work_fin-b01_20261006_fix7-150" / "FIN3-WKN-150" / "跑分产物与轨迹"

for source, label in [(REJ / "oracle" / "verifier", "new"), (ARCH / "oracle", "old")]:
    details = source / "reward-details.json" if label == "old" else source / "graded" / "reward.json"
    reward = source / "reward.json"
    print(f"=== {label} {reward}")
    print(reward.read_text(encoding="utf-8"))
    if details.is_file():
        data = json.loads(details.read_text(encoding="utf-8"))
        reward_data = data.get("reward", data)
        if not isinstance(reward_data, dict):
            reward_data = data
        criteria = reward_data.get("criteria", [])
        if isinstance(reward_data, dict) and "score" in reward_data:
            print("score=", reward_data.get("score"))
        for criterion in criteria:
            if isinstance(criterion, dict) and float(criterion.get("value") or 0) < 1:
                print(criterion["id"], criterion.get("value"), criterion.get("raw"))
                print(" ", criterion.get("reasoning", "")[:1000])
    print()
