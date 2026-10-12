#!/bin/bash
# FIN3-WKN-153 qwen 第 4 次尝试（2026-10-12 19:00 起）的只读监控。
# 前三次均因判官侧故障失败（网关断连 / 单条判据死循环），本次监控重点：
#   1) trial 是否退出（qwen.log 出现 EXIT=）；
#   2) 容器内 claude 会话数是否增长（判官 individual 模式：每条判据一个会话）；
#   3) 最新会话内 StructuredOutput 出现次数（>15 且增长 = 死循环，见 07-pitfalls A11）。
# 用法: bash watch_qwen_153_r4.sh [最大轮数，默认 240 轮 × 60s = 4h]
set -u
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
LOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/qwen.log
TRIAL=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/trials/qwen38max-153
WATCHLOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/watch.log
MAX=${1:-240}

# 同时落盘，避免 stdio 管道块缓冲导致看起来"没有进度"（*.log 已被 .gitignore 忽略）
say() { echo "$1"; echo "$1" >> "$WATCHLOG"; }

for i in $(seq 1 "$MAX"); do
  ts=$(date '+%F %T')
  if grep -q '^EXIT=' "$LOG" 2>/dev/null; then
    say "[$ts] DONE $(grep '^EXIT=' "$LOG" | tail -1)"
    break
  fi
  alive=no
  pgrep -f 'harbor trial start' >/dev/null 2>&1 && alive=yes
  c=$(docker ps --format '{{.Names}}' 2>/dev/null | grep 'qwen38max-153' | head -1)
  sess=-; so=-; last=-; jsn=-
  if [ -n "$c" ]; then
    sess=$(docker exec "$c" bash -lc 'ls -1 /root/.claude/projects/-app/*.jsonl 2>/dev/null | wc -l' 2>/dev/null)
    jsn=$(docker exec "$c" bash -lc 'ls -1t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1 | xargs -r basename' 2>/dev/null)
    so=$(docker exec "$c" bash -lc 'f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1); [ -n "$f" ] && grep -o "StructuredOutput" "$f" | wc -l || echo 0' 2>/dev/null)
    last=$(docker exec "$c" bash -lc 'f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1); [ -n "$f" ] && stat -c "%s@%y" "$f" | cut -c1-40 || echo none' 2>/dev/null)
  fi
  nout=$(ls -1 "$TRIAL/artifacts/app/output" 2>/dev/null | wc -l)
  say "[$ts] alive=$alive container=${c:-none} sessions=${sess} structOut=${so} out=${nout} newest=${jsn} size/time=${last}"
  sleep 60
done
say "[$(date '+%F %T')] watcher exit"
