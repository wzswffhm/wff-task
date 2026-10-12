#!/bin/bash
# 确认 qwen 当前处于 agent 阶段还是判分阶段
C=qwen38max-153__env-main-1
docker ps --format '{{.Names}}|{{.Status}}' | grep "^$C" || { echo "容器未运行"; exit 0; }
docker exec "$C" bash -lc '
  echo "容器时间: $(date "+%H:%M:%S")"
  echo "--- 进程（agent=stream-json；judge=claude -p）---"
  ps -eo pid,etime,pcpu,cmd 2>/dev/null | grep -E "claude|rewardkit" | grep -v grep | cut -c1-95
  echo "--- /logs 结构 ---"
  ls -la /logs/agent/ /logs/verifier/ 2>/dev/null | head -14
  echo "--- agent 轨迹写入时间 ---"
  ls -l --time-style=+%H:%M:%S /logs/agent/*.txt 2>/dev/null | tail -2
  echo "--- 判分会话目录数 ---"
  ls -1d /tmp/claude-0/-app/*/ 2>/dev/null | wc -l
' 2>/dev/null
