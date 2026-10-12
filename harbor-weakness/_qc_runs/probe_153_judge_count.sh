#!/bin/bash
# 统计判分进度：rewardkit 每条判据起一个 claude 会话，会话目录位于 /tmp/claude-0/-app/<uuid>/
for c in gpt56sol-153__env-main-1 qwen38max-153__env-main-1; do
  echo "=== $c ==="
  docker ps --format '{{.Names}}|{{.Status}}' | grep "^$c" || { echo "  (未运行)"; continue; }
  docker exec "$c" bash -lc '
    n=$(ls -1d /tmp/claude-0/-app/*/ 2>/dev/null | wc -l)
    echo "  已生成判分会话目录: $n"
    echo "  最近 5 个（按时间）:"
    ls -1dt /tmp/claude-0/-app/*/ 2>/dev/null | head -5 | while read -r d; do
      printf "    %s  %s\n" "$(date -r "$d" "+%H:%M:%S")" "$(basename "$d" | cut -c1-8)"
    done
    echo "  判分过程文件:"
    ls -la /logs/verifier/graded/ 2>/dev/null | tail -4
  ' 2>/dev/null
done
echo "=== 宿主侧 trial 时间线 ==="
for t in gpt56sol-153 qwen38max-153; do
  d="/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-153-$( [ "$t" = "gpt56sol-153" ] && echo gpt || echo qwen )/trials/$t"
  echo "[$t] $(ls -la "$d" 2>/dev/null | grep -c .) 个条目；verifier: $(ls "$d/verifier" 2>/dev/null | tr '\n' ' ')"
done
date "+now %H:%M:%S"
