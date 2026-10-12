#!/bin/bash
# 停止旧的 qwen 重判看守（它仍在等 opus，已不适用）
PIDS=$(pgrep -f 'g5_153_regrade_qwen' | grep -v "^$$\$")
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -TERM "-$pgid" 2>/dev/null
done
sleep 2
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -KILL "-$pgid" 2>/dev/null
done
echo "--- remaining regrade/watchdog ---"
ps -eo pid,cmd | grep -E 'g5_153_regrade_qwen|watchdog_153b' | grep -v grep || echo none
echo "--- gpt status ---"
docker ps --format '{{.Names}}|{{.Status}}'
pgrep -af 'gpt56sol-153' | head -2 || echo "no gpt harbor proc"
