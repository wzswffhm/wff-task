#!/bin/bash
# 切换到并行判分：停止等待型看守，立即启动 qwen 重判
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

# 1) 停止 watchdog_153b（它会等 gpt 结束才重判，已不需要）
for p in $(pgrep -f 'watchdog_153b.sh' | grep -v "^$$\$"); do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -TERM "-$pgid" 2>/dev/null
done
sleep 2
for p in $(pgrep -f 'watchdog_153b.sh' | grep -v "^$$\$"); do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -KILL "-$pgid" 2>/dev/null
done
echo "watchdog-b: $(pgrep -cf 'watchdog_153b.sh' || echo 0) 个残留"

# 2) 立即启动 qwen 重判（并行）
cd "$Q" || exit 90
setsid nohup bash g5_153_regrade_now.sh > /dev/null 2>&1 < /dev/null &
sleep 12
echo "--- regrade log ---"
tail -5 "$Q/g5-153-qwen/regrade-now.log" 2>/dev/null || echo "(no log yet)"
echo "--- procs ---"
ps -eo pid,etime,cmd | grep -E 'regrade_now|harbor trial (start|regrade)' | grep -v grep | cut -c1-110
echo "--- containers ---"
docker ps --format '{{.Names}}|{{.Status}}'
