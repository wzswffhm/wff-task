#!/bin/bash
# 终止被误调度的 opus 执行体（甲方 2026-10-12 指示：opus 端点有问题，暂不跑）
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
echo "宿主时间: $(date '+%H:%M:%S')"
echo "--- 终止前 ---"
ps -eo pid,pgid,etime,cmd | grep -E 'opus48-153|hub.*opus' | grep -v grep | cut -c1-110
docker ps --format '{{.Names}}|{{.Status}}' | grep opus || echo "  (无 opus 容器)"

for p in $(pgrep -f 'opus48-153' | grep -v "^$$\$"); do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -TERM "-$pgid" 2>/dev/null
done
sleep 3
for p in $(pgrep -f 'opus48-153' | grep -v "^$$\$"); do
  pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
  [ -n "${pgid:-}" ] && kill -KILL "-$pgid" 2>/dev/null
done
for c in $(docker ps -a --format '{{.Names}}' | grep 'opus48-153'); do
  docker rm -f "$c" >/dev/null 2>&1 && echo "  已删除容器 $c"
done
echo "[$(date '+%F %T')] opus 已终止（甲方指示暂不跑）" >> "$Q/g5-153-opus/OPUS_ABORTED.txt"

sleep 2
echo "--- 终止后 ---"
ps -eo pid,etime,cmd | grep -E 'opus48-153' | grep -v grep | cut -c1-90 || echo "  无残留 opus 进程"
docker ps --format '{{.Names}}|{{.Status}}' || true
echo "--- qwen 重跑状态（应不受影响）---"
docker ps --format '{{.Names}}|{{.Status}}' | grep qwen || echo "  qwen 容器未运行"
