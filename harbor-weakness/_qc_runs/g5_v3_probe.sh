#!/bin/bash
# 确认两模型是否真进了判分 / 还卡在 agent 收尾
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
for spec in \
  "qwen:qwen38max-152v3__env-main-1:g5-152v3-qwen" \
  "gpt:gpt56sol-152v3__env-main-1:g5-152v3-gpt" ; do
  label="${spec%%:*}"; r1="${spec#*:}"; c="${r1%%:*}"; dir="${r1##*:}"
  echo "=== $label ==="
  echo -n "  service: "; systemctl is-active "g5-v3-${label}.service" 2>/dev/null
  echo -n "  轨迹大小: "; docker exec "$c" sh -c 'wc -c < /logs/agent/claude-code.txt 2>/dev/null' 2>/dev/null
  echo -n "  agent进程: "; docker exec "$c" sh -c "ps -eo args --no-headers | grep -c 'claude --verbose'" 2>/dev/null
  echo -n "  判官进程: "; docker exec "$c" sh -c "ps -eo args --no-headers | grep -c 'claude -p'" 2>/dev/null
  echo -n "  agent结果最后事件: "; tail -c 400 "$Q/$dir/trials"/*/agent/claude-code.txt 2>/dev/null | grep -oE '"type":"result"|"subtype":"success"|"terminal_reason":"[a-z]+"' | tail -3 | tr '\n' ' '; echo
  echo -n "  graded: "; docker exec "$c" sh -c 'ls /logs/verifier/graded/ 2>/dev/null | wc -l' 2>/dev/null
  echo -n "  reward: "; find "$Q/$dir/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; done; echo
done
date '+%F %T'
