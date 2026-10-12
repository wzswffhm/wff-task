#!/bin/bash
# 停止 G5 运行（按进程组）
PIDS=$(pgrep -f 'g5_153_run' | grep -v "^$$\$")
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -TERM "-$pgid" 2>/dev/null
done
sleep 3
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -KILL "-$pgid" 2>/dev/null
done
# 兜底：杀掉残留 harbor trial 进程与容器
for p in $(pgrep -f 'harbor trial start' 2>/dev/null); do kill -KILL "$p" 2>/dev/null; done
sleep 1
for c in $(docker ps -a --format '{{.Names}}' | grep -E 'qwen38max-153|oracle-153'); do docker rm -f "$c" >/dev/null 2>&1; done
echo "--- remaining ---"
ps -eo pid,pgid,cmd | grep -E 'g5_153_run|harbor trial start' | grep -v grep || echo none
echo "--- containers ---"
docker ps -a --format '{{.Names}}|{{.Status}}' | head -4
echo "--- watchdog ---"
pgrep -af watchdog_153 | head -2 || echo "no watchdog"
