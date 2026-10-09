#!/bin/bash
# v3 qwen/gpt 判分明细：为何满分？核验判据 R30-R33 到底过没过
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
for spec in "qwen:g5-152v3-qwen" "gpt:g5-152v3-gpt" ; do
  label="${spec%%:*}"; dir="${spec##*:}"
  echo "=== $label ==="
  rj=$(find "$R/$dir/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  echo -n "  reward: "; tr -d '\n' < "$rj" 2>/dev/null; echo
  F=$(find "$R/$dir/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
  if [ -n "$F" ]; then
    python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
crit = d.get("reward", {}).get("criteria", [])
print(f"  条数={len(crit)} score={d.get('reward',{}).get('score')}")
zero = [c for c in crit if float(c.get("value") or 0) == 0]
print(f"  value=0 的条数={len(zero)}: {[c['id'] for c in zero]}")
# 核验判据
for c in crit:
    if c["id"] in ("R30","R31","R32","R33","R13","R19","R18"):
        print(f"    {c['id']} value={c.get('value')} raw={c.get('raw')} w={c.get('weight')}")
PY
  else
    echo "  (无 reward-details.json)"
  fi
done
