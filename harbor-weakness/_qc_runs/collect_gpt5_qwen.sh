#!/bin/bash
# 收集 gpt 第5轮 / qwen 第2轮最终结果
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

echo "=== services ==="
for s in g5-qwen-152v2 g5-gpt-152v2 g5-gpt5-152v2 g4-152v3; do
  printf '  %-18s %s\n' "$s" "$(systemctl is-active $s.service 2>/dev/null)"
done

echo
echo "=== gpt 第5轮 reward ==="
find "$R/g5-152v2-gpt5/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do
  tr -d '\n' < "$f"; echo
done
echo "=== qwen 第2轮 reward ==="
find "$R/g5-152v2-qwen2/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do
  tr -d '\n' < "$f"; echo
done

echo
echo "=== gpt 第5轮失分项 ==="
F=$(find "$R/g5-152v2-gpt5/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
if [ -n "$F" ]; then
  python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
crit = d.get("reward", {}).get("criteria", [])
lost = [c for c in crit if float(c.get("value") or 0) == 0]
print(f"  score={d.get('reward',{}).get('score')} 失分={len(lost)}/{len(crit)}")
for c in lost:
    print(f"    [失] {c['id']} w={c.get('weight')}")
PY
else
  echo "  (无 reward-details.json)"
fi

echo
echo "=== 容器 ==="
docker ps --format '{{.Names}} | {{.Status}}'
