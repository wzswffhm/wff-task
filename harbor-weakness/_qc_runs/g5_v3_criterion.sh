#!/bin/bash
# 抓当前判据：判官进程命令行里常带 "- 'Rxx'"，也可能是别的形式，宽松匹配
for spec in \
  "qwen:qwen38max-152v3__env-main-1" \
  "gpt:gpt56sol-152v3__env-main-1" ; do
  label="${spec%%:*}"; c="${spec##*:}"
  echo "=== $label ==="
  # 找 claude -p 判官进程，抓其完整命令行里第一个 Rxx/Nxx
  line=$(docker exec "$c" sh -c "ps -eo etimes,args --no-headers | grep 'claude -p' | grep -v grep | head -1" 2>/dev/null)
  echo "  判官行(前160): $(echo "$line" | cut -c1-160)"
  cid=$(echo "$line" | grep -oE "[RN][0-9]{2}" | head -1)
  age=$(echo "$line" | awk '{print $1}')
  echo "  当前判据: ${cid:-未识别}  本条耗时: ${age:-?}s"
done
