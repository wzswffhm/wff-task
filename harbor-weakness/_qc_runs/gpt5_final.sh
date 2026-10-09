#!/bin/bash
# gpt5 最终成绩
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
echo "=== gpt5 reward ==="
find "$R/g5-152v2-gpt5/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; echo; done
echo "=== gpt5 reward_exit ==="
find "$R/g5-152v2-gpt5/trials" -maxdepth 3 -name reward_exit_message.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; echo; done
echo "=== gpt5 明细 ==="
F=$(find "$R/g5-152v2-gpt5/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
if [ -n "$F" ]; then
  python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
crit = d.get("reward", {}).get("criteria", [])
lost = [c for c in crit if float(c.get("value") or 0) == 0]
print(f"  details.score={d.get('reward',{}).get('score')} 条数={len(crit)} 失分={len(lost)}")
for c in lost:
    print(f"    [失] {c['id']} w={c.get('weight')} | {(c.get('description') or '')[:60]}")
PY
else
  echo "  (无 reward-details.json)"
fi
echo "=== G4 v3 reward ==="
find "$R/g4-152v3/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; echo; done
