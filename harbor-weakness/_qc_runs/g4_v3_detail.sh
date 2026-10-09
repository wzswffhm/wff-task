#!/bin/bash
# oracle v3 判分明细
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4-152v3
F=$(find "$R/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
if [ -n "$F" ]; then
  python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
crit = d.get("reward", {}).get("criteria", [])
lost = [c for c in crit if float(c.get("value") or 0) == 0]
print(f"score={d.get('reward',{}).get('score')} 条数={len(crit)} 失分={len(lost)}")
for c in lost:
    print(f"  [失] {c['id']} w={c.get('weight')} | {(c.get('description') or '')[:70]}")
# 新判据 R30-R33 得分
print("--- 新核验判据 R30-R33 ---")
for c in crit:
    if c["id"] in ("R30","R31","R32","R33"):
        print(f"  {c['id']} value={c.get('value')} raw={c.get('raw')} w={c.get('weight')}")
PY
else
  echo "(无 reward-details.json)"
fi
