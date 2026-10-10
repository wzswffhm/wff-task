# -*- coding: utf-8 -*-
"""查 oracle 扣分判据 R26/R33 的判官评语，以及 qwen 对同两条的评语。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs")
SRC = {
    "oracle": Q / "g4-152v3" / "trials" / "oracle-152v3" / "verifier" / "reward-details.json",
    "qwen": Q / "g5-152v3-qwen" / "trials" / "qwen38max-152v3" / "verifier" / "reward-details.json",
    "gpt": Q / "g5-152v3-gpt" / "trials" / "gpt56sol-152v3" / "verifier" / "reward-details.json",
}
for ex, p in SRC.items():
    if not p.exists():
        print(f"{ex}: 缺 {p}")
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    crits = j["reward"]["criteria"]
    print("=" * 104)
    print(f"{ex}  score={j['reward'].get('score')}")
    for c in crits:
        if c["id"] in ("R26", "R33"):
            print(f"  --- {c['id']}  value={c.get('value')}  weight={c.get('weight')} ---")
            print(f"  desc: {str(c.get('description',''))[:600]}")
            print(f"  reasoning: {str(c.get('reasoning',''))[:900]}")
            print()
