#!/usr/bin/env bash
echo "=== 时间: $(date '+%F %T') ==="
echo "=== oracle 输出 tail ==="
tail -25 /home/wff/harbor-runs/FIN3-WKN-149-fix9/oracle_fix9.out 2>/dev/null
echo ""
echo "=== trials-oracle 目录 ==="
ls -la /home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle/ 2>/dev/null
echo "=== 最新 trial 内的进度 ==="
for t in /home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle/*/; do
  [ -d "$t" ] || continue
  echo "--- $(basename $t) ---"
  ls "$t" 2>/dev/null
  if [ -f "$t/verifier/reward.json" ]; then
    echo "REWARD: $(cat $t/verifier/reward.json)"
  fi
  if [ -f "$t/result.json" ]; then
    echo "RESULT: $(head -c 400 $t/result.json)"
  fi
done
echo ""
echo "=== 容器 ==="
docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -i fin3 || echo "(无)"
echo "=== judge 进程 ==="
ps aux | grep -E 'rewardkit|judge' | grep -v grep | head -5 || echo "(无)"
