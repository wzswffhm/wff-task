#!/bin/bash
# 停止 G4 运行（按进程组，避免 pkill 自杀）
PIDS=$(pgrep -f 'g4_153_run' | grep -v "^$$\$")
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  if [ -n "${pgid:-}" ]; then
    kill -TERM "-$pgid" 2>/dev/null
  fi
done
sleep 3
for p in $PIDS; do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  if [ -n "${pgid:-}" ]; then
    kill -KILL "-$pgid" 2>/dev/null
  fi
done
sleep 1
docker rm -f oracle-153__env-main-1 >/dev/null 2>&1
echo "--- remaining ---"
ps -eo pid,pgid,cmd | grep -E 'g4_153_run|harbor trial start' | grep -v grep || echo none
echo "--- containers ---"
docker ps -a --format '{{.Names}}|{{.Status}}' | head -3
