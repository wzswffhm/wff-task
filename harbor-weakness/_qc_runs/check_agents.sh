#!/bin/bash
# 检查两个 agent 容器是否在真实推进
for c in gpt56sol3-152v2__env-main-1 qwen38max-152v2__env-main-1; do
  echo "=== $c ==="
  docker exec "$c" ps -eo etimes,args --no-headers 2>/dev/null | grep claude | grep -v grep | head -2
  echo -n "  claude-code.txt bytes: "
  docker exec "$c" sh -c 'wc -c < /logs/agent/claude-code.txt 2>/dev/null' 2>/dev/null || echo "?"
  echo -n "  /app/output files: "
  docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null || echo "?"
done
