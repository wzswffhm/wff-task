#!/bin/bash
# 紧凑进度快照：判分条数、容器状态、日志尾、reward 读数
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
date "+=== now %H:%M:%S ==="
for pair in "gpt:gpt56sol-153:g5-153-gpt:gpt.log" "qwen:qwen38max-153:g5-153-qwen:qwen.log"; do
  IFS=: read -r tag trial dir log <<< "$pair"
  c="${trial}__env-main-1"
  echo "--- $tag ($trial) ---"
  st=$(docker ps --format '{{.Names}}|{{.Status}}' | grep "^$c" || true)
  if [ -n "$st" ]; then
    echo "  容器: $st"
    cnt=$(docker exec "$c" bash -lc 'ls -1d /tmp/claude-0/-app/*/ 2>/dev/null | wc -l' 2>/dev/null)
    echo "  判分会话数: ${cnt:-?}/34"
  else
    echo "  容器: 未运行"
  fi
  rp="$Q/$dir/trials/$trial/verifier/reward.json"
  if [ -f "$rp" ]; then
    echo "  reward: $(tr -d '\n ' < "$rp")"
  else
    echo "  reward: (尚未生成)"
  fi
  lg="$Q/$dir/$log"
  [ -f "$lg" ] && echo "  日志尾: $(grep -E '^(EXIT=|Rewards:|Finished:)' "$lg" | tail -2 | tr '\n' ' ')"
done
