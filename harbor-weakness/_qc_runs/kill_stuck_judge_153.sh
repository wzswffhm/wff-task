#!/bin/bash
# 终止 qwen 判分中失控的单条 claude 会话，观察 rewardkit 是否继续后续判据
C=qwen38max-153__env-main-1
echo "宿主时间: $(date '+%H:%M:%S')"
docker exec "$C" bash -lc '
  echo "容器时间: $(date "+%H:%M:%S")"
  echo "--- 干预前 ---"
  ps -eo pid,etime,pcpu,cmd | grep "claude -p" | grep -v grep | cut -c1-70
  pids=$(pgrep -f "claude -p" || true)
  for p in $pids; do
    kill -TERM "$p" 2>/dev/null && echo "  sent TERM to $p"
  done
  sleep 5
  pids2=$(pgrep -f "claude -p" || true)
  for p in $pids2; do
    kill -KILL "$p" 2>/dev/null && echo "  sent KILL to $p"
  done
  sleep 3
  echo "--- 干预后进程 ---"
  ps -eo pid,etime,cmd | grep -E "claude|rewardkit" | grep -v grep | cut -c1-70
' 2>/dev/null
sleep 20
echo "--- 20 秒后（宿主视角）---"
docker exec "$C" bash -lc 'ls -1d /tmp/claude-0/-app/*/ 2>/dev/null | wc -l; ps -eo etime,cmd | grep -E "claude|rewardkit" | grep -v grep | cut -c1-60' 2>/dev/null
