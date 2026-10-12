#!/usr/bin/env bash
echo "=== 文档内批次名分布 ==="
D=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261011_fix10-149/交付文档.md
grep -n 'work_fin-b01_' "$D" | sed 's/\(.\{140\}\).*/\1.../' || echo "(无)"
echo ""
echo "=== fix10 批次结构 ==="
find /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261011_fix10-149 -maxdepth 2 | sed 's|.*fix10-149|fix10-149|' | sort | head -20
echo ""
echo "=== oracle fix10 进度 ==="
T=/home/wff/harbor-runs/FIN3-WKN-149-fix10/trials-oracle
ls "$T" 2>/dev/null
for d in "$T"/*/; do
  [ -d "$d" ] || continue
  echo "--- $(basename "$d")"
  cat "$d/verifier/reward.json" 2>/dev/null
  echo ""
  echo -n "  当前判据: "
  C=$(basename "$d" | tr 'A-Z' 'a-z')
  docker exec "fin3-wkn-149__${C#fin3-wkn-149__}__env-main-1" ps aux 2>/dev/null | grep -oE "\- '(R|N)[0-9]+'" | tail -1 || echo "?"
done
echo ""
echo "=== 容器 ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -i 149 || echo "(无)"
