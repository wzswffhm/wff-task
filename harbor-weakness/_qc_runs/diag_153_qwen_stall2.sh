#!/bin/bash
# 深入诊断卡住的判官会话：网络连接、日志写入、进程树
C=qwen38max-153__env-main-1
docker exec "$C" bash -lc '
  echo "容器时间(UTC): $(date "+%H:%M:%S")"
  echo "--- claude 进程树 ---"
  ps -eo pid,ppid,etime,stat,pcpu,cmd 2>/dev/null | grep -E "claude|rewardkit|python" | grep -v grep | cut -c1-110 | head -8
  echo "--- 最近的会话 jsonl（修改时间）---"
  ls -lt --time-style=+%H:%M:%S /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -4
  echo "--- 对外连接 ---"
  (ss -tnp 2>/dev/null || netstat -tnp 2>/dev/null) | grep -E "ESTAB|SYN" | head -8
  echo "--- 卡住会话的末尾记录（截断）---"
  f=$(ls -t /root/.claude/projects/-app/*.jsonl 2>/dev/null | head -1)
  [ -n "$f" ] && tail -c 600 "$f"
' 2>/dev/null
