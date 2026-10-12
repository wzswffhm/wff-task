#!/usr/bin/env bash
T=/home/wff/harbor-runs/FIN3-WKN-149-fix10/trials-oracle
echo "时间: $(date '+%F %T')"
echo "=== oracle.out 尾 ==="
tail -20 /home/wff/harbor-runs/FIN3-WKN-149-fix10/oracle.out
echo ""
echo "=== trials 目录 ==="
ls -la "$T"/
echo ""
for d in "$T"/*/; do
  [ -d "$d" ] || continue
  echo "--- $(basename "$d")  mtime=$(stat -c%y "$d" | cut -d. -f1)"
  echo "  文件: $(ls "$d" | tr '\n' ' ')"
  echo "  trial.log 尾:"
  tail -6 "$d/trial.log" 2>/dev/null | sed 's/^/    /'
  echo "  artifacts/app/output:"
  ls -la "$d/artifacts/app/output/" 2>/dev/null | tail -8 | sed 's/^/    /'
  echo "  图表哈希(oci):"
  for f in "$d/artifacts/app/output/FIN3-WKN-149_charts"/*.png; do
    [ -f "$f" ] && echo "    $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
  done
done
echo ""
echo "=== 容器 ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -i 149 || echo "(无)"
echo "=== judge 进程 ==="
ps -eo etime,cmd | grep '[r]ewardkit' | head -3
