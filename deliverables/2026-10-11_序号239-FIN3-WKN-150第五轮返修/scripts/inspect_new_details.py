# -*- coding: utf-8 -*-
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
REJ = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150\_rejudge")
ARCH = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness"
                    r"\work_fin-b01_20261006_fix7-150\FIN3-WKN-150\跑分产物与轨迹")


def criteria_map(path: pathlib.Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    reward = data.get("reward", data)
    if not isinstance(reward, dict):
        raise ValueError(f"unexpected {path}: {reward!r}")
    criteria = reward.get("criteria") or []
    return reward, {c["id"]: c for c in criteria if isinstance(c, dict) and "id" in c}


for ex in ["oracle", "qwen3.8-max-0902", "claude-opus-4-8"]:
    new_path = REJ / ex / "verifier" / "reward-details.json"
    old_path = ARCH / ex / "reward-details.json"
    print("===", ex)
    if not new_path.exists():
        print("  no new details")
        continue
    new_reward, new = criteria_map(new_path)
    old_reward, old = criteria_map(old_path) if old_path.exists() else ({}, {})
    print(f"  new score={new_reward.get('score')} old score={old_reward.get('score')}")
    for cid, new_item in sorted(new.items()):
        old_item = old.get(cid, {})
        if float(new_item.get("value") or 0) != float(old_item.get("value") or 0):
            print(f"  {cid}: old={old_item.get('value')} new={new_item.get('value')}")
            print("    OLD:", str(old_item.get("reasoning", ""))[:700])
            print("    NEW:", str(new_item.get("reasoning", ""))[:700])
    print()
