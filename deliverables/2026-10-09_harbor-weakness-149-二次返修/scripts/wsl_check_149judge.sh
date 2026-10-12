#!/usr/bin/env bash
echo "=== 时间: $(date '+%F %T') ==="
echo "=== 149 oracle 判分进度 ==="
# rewardkit 是否还在
ps aux | grep -E 'FIN3-WKN-149|rewardkit' | grep -v grep | grep -v FIN3-WKN-150 | head -5
echo ""
echo "=== 149 oracle trial 内 verifier 状态 ==="
T=/home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle/FIN3-WKN-149__DRcKq7u
ls -la "$T/verifier/" 2>/dev/null
echo "--- graded 目录 ---"
ls -la "$T/verifier/graded/" 2>/dev/null
echo "--- reward.json ---"
cat "$T/verifier/reward.json" 2>/dev/null
echo ""
echo "--- reward-details 是否在写 ---"
if [ -f "$T/verifier/graded/reward-details.json" ]; then
  echo "reward-details 大小: $(stat -c%s $T/verifier/graded/reward-details.json) B"
fi
echo ""
echo "=== 容器状态 ==="
docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep -E 'fin3-wkn-149|rejudge' | head
echo ""
echo "=== 149 oracle trial.log tail ==="
tail -8 "$T/trial.log" 2>/dev/null
