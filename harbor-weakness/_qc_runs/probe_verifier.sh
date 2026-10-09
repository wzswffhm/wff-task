#!/bin/bash
# 探测容器内判分日志位置，以便按"场次/判据进度/得分/状态/尝试"报告
for c in gpt56sol4-152v2__env-main-1 qwen38max2-152v2__env-main-1; do
  echo "########## $c ##########"
  echo "--- /logs 顶层 ---"
  docker exec "$c" sh -c 'ls -la /logs/ 2>/dev/null' 2>&1
  echo "--- /logs/verifier ---"
  docker exec "$c" sh -c 'ls -la /logs/verifier/ 2>/dev/null | head -12' 2>&1
  echo "--- /logs/agent 文件 ---"
  docker exec "$c" sh -c 'ls -la /logs/agent/ 2>/dev/null | head -8' 2>&1
  echo "--- /app/output 产物 ---"
  docker exec "$c" sh -c 'ls -la /app/output/ 2>/dev/null | head -12' 2>&1
  echo "--- 当前进程（claude / judge / pytest） ---"
  docker exec "$c" sh -c 'ps -eo etimes,args --no-headers 2>/dev/null | grep -E "claude|pytest|test.sh|reward" | grep -v grep | head -5' 2>&1
  echo
done
