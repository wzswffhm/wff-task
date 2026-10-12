#!/bin/bash
# 探测 gpt / qwen 判分进度（只读，不干扰）
for c in gpt56sol-153__env-main-1 qwen38max-153__env-main-1; do
  echo "=== $c ==="
  if ! docker ps --format '{{.Names}}' | grep -q "^$c$"; then
    echo "  (容器未运行)"
    continue
  fi
  docker exec "$c" bash -lc '
    echo "-- /logs/verifier --"
    ls -la /logs/verifier/ 2>/dev/null | head -12
    echo "-- 判分工作目录候选 --"
    find /logs /tmp /root /app -maxdepth 4 -type d \( -iname "*rejudge*" -o -iname "*reward*" -o -iname "*graded*" \) 2>/dev/null | head -8
    echo "-- 已写出的判分条目文件 --"
    find / -maxdepth 5 -type f \( -name "reward-details.json" -o -name "*criterion*.json" -o -name "judgment*.json" \) 2>/dev/null | head -8
    echo "-- claude 判分调用痕迹（每条的 stdout 目录） --"
    find /tmp /logs -maxdepth 4 -type d -newermt "-90 minutes" 2>/dev/null | head -10
  ' 2>/dev/null
done
