#!/bin/bash
# FIN3-WKN-153 G5 opus（claude-opus-4-8 @ 4router.net）跑分的只读监控。
# 关注：① trial 是否退出（opus.log 出现 EXIT=）；
#       ② 判官 individual 模式会话数是否随 34 条判据推进（agent 段结束后开始增长）；
#       ③ 最新会话 StructuredOutput 次数（>15 且增长 = A11 死循环）；
#       ④ agent 段是否出现 403 余额/鉴权类报错（上次失败模式）。
# 用法: bash watch_opus_153.sh [最大轮数，默认 300 轮 × 60s = 5h]
set -u
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
LOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-opus/opus.log
TRIAL=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-opus/trials/opus48-153
WATCHLOG=$TASK_ROOT/harbor-weakness/_qc_runs/g5-153-opus/watch.log
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
  c=$(docker ps --format '{{.Names}}' 2>/dev/null | grep 'opus48-153' | head -1)
  sess=-; so=-; sz=-; nout=-; err=-
  if [ -n "$c" ]; then
    sess=$(docker exec "$c" bash -lc 'ls -1 /root/.claude/projects/-app/*.jsonl 2>/dev/null | wc -l' 2>/dev/null)
    so=$(docker exec "$c" bash -lc 'f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1); [ -n "$f" ] && grep -o "StructuredOutput" "$f" | wc -l || echo 0' 2>/dev/null)
    sz=$(docker exec "$c" bash -lc 'f=$(ls -l /logs/agent/claude-code.txt 2>/dev/null); echo "$f" | awk "{print \$5}"' 2>/dev/null)
    nout=$(docker exec "$c" bash -lc 'ls -1 /app/output 2>/dev/null | wc -l' 2>/dev/null)
    err=$(docker exec "$c" bash -lc 'grep -o "Insufficient account balance\|API-key is blocked\|authentication_error" /logs/agent/claude-code.txt 2>/dev/null | tail -1' 2>/dev/null)
  fi
  say "[$ts] alive=$alive container=${c:-none} sessions=${sess} structOut=${so} agentLog=${sz}B out=${nout} err=${err:-none}"
  sleep 60
done
say "[$(date '+%F %T')] watcher exit"
