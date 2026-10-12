#!/bin/bash
# FIN3-WKN-153 qwen verifier-only 重判（trial: qwen38max-153-reg1）的只读监控。
# 关注：① trial 是否退出（regrade_v2.log 出现 EXIT=）；
#       ② 判官 individual 模式会话数是否随判据推进增长（34 条判据 → 会话数趋向 34）；
#       ③ 最新会话 StructuredOutput 次数（>15 且增长 = A11 死循环）。
# 用法: bash watch_qwen_153_reg1.sh [最大轮数，默认 300 轮 × 60s = 5h]
set -u
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
LOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/regrade_v2.log
TRIAL=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/trials/qwen38max-153-reg1
WATCHLOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-qwen/watch_reg1.log
MAX=${1:-300}

say() { echo "$1"; echo "$1" >> "$WATCHLOG"; }

for i in $(seq 1 "$MAX"); do
  ts=$(date '+%F %T')
  if grep -q '^EXIT=' "$LOG" 2>/dev/null; then
    say "[$ts] DONE $(grep '^EXIT=' "$LOG" | tail -1)"
    break
  fi
  alive=no
  pgrep -f 'harbor trial start' >/dev/null 2>&1 && alive=yes
  c=$(docker ps --format '{{.Names}}' 2>/dev/null | grep 'qwen38max-153-reg1' | head -1)
  sess=-; so=-; jsn=-; sz=-
  if [ -n "$c" ]; then
    sess=$(docker exec "$c" bash -lc 'ls -1 /root/.claude/projects/-app/*.jsonl 2>/dev/null | wc -l' 2>/dev/null)
    jsn=$(docker exec "$c" bash -lc 'ls -1t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1 | xargs -r basename' 2>/dev/null)
    so=$(docker exec "$c" bash -lc 'f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1); [ -n "$f" ] && grep -o "StructuredOutput" "$f" | wc -l || echo 0' 2>/dev/null)
    sz=$(docker exec "$c" bash -lc 'f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1); [ -n "$f" ] && stat -c "%s" "$f" || echo none' 2>/dev/null)
  fi
  say "[$ts] alive=$alive container=${c:-none} sessions=${sess} structOut=${so} newestSize=${sz} newest=${jsn}"
  sleep 60
done
say "[$(date '+%F %T')] watcher exit"
