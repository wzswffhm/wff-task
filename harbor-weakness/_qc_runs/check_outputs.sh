#!/bin/bash
# 三场次进度 + 产物实况 + gpt4 判分明细
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

bash "$R/progress_3x.sh" 2>&1 | head -12

echo
echo "=== 各容器 /app/output 实况 ==="
for c in gpt56sol5-152v2__env-main-1 gpt56sol4-152v2__env-main-1 qwen38max2-152v2__env-main-1; do
  n=$(docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null)
  echo "  $c -> ${n:-?} 个文件"
  docker exec "$c" sh -c 'ls /app/output 2>/dev/null' 2>/dev/null | sed 's/^/      /'
done

echo
echo "=== gpt 第4轮判分明细（为什么 0 分） ==="
F=$(find "$R/g5-152v2-gpt4/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
if [ -n "$F" ]; then
  python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("reward", {})
crit = r.get("criteria", [])
print(f"  总分 = {r.get('score')}   条数 = {len(crit)}")
hit = [c for c in crit if float(c.get("value") or 0) > 0]
print(f"  得分条数 = {len(hit)} / {len(crit)}")
for c in crit[:6]:
    desc = (c.get("description") or "")[:70].replace("\n", " ")
    print(f"    {c['id']} value={c.get('value')} raw={c.get('raw')} w={c.get('weight')} | {desc}")
PY
else
  echo "  (无 reward-details.json)"
fi

echo
echo "=== qwen 是否已出分 ==="
find "$R/g5-152v2-qwen2/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; echo; done
