#!/bin/bash
# qwen 第2轮结果 + 全部场次状态
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

bash "$R/progress_3x.sh" 2>&1 | head -12

echo
echo "=== services ==="
for s in g5-qwen-152v2 g5-gpt-152v2 g5-gpt5-152v2; do
  printf '  %-20s %s\n' "$s" "$(systemctl is-active $s.service)"
done

echo
echo "=== qwen 第2轮 reward.json ==="
find "$R/g5-152v2-qwen2/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do
  echo "  $f"
  cat "$f"
done

echo
echo "=== qwen 第2轮判分明细 ==="
F=$(find "$R/g5-152v2-qwen2/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
if [ -n "$F" ]; then
  python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("reward", {})
crit = r.get("criteria", [])
print(f"  details.score = {r.get('score')}  条数 = {len(crit)}")
pos = [c for c in crit if c['id'].startswith('R')]
neg = [c for c in crit if c['id'].startswith('N')]
hit = [c for c in pos if float(c.get("value") or 0) > 0]
print(f"  正向得分条数 = {len(hit)}/{len(pos)}   负向触发扣分 = {sum(1 for c in neg if float(c.get('value') or 0)==0)}/{len(neg)}")
print("  正向未得分项:", ", ".join(c['id'] for c in pos if float(c.get('value') or 0)==0) or "(无)")
PY
else
  echo "  (无 reward-details.json)"
fi

echo
echo "=== 产物对照 ==="
find "$R/g5-152v2-qwen2/trials" -path "*artifacts/app/output*" -type f 2>/dev/null | wc -l
