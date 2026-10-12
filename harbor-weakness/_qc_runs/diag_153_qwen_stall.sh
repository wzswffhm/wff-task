#!/bin/bash
# 诊断 qwen 判分是否停滞
C=qwen38max-153__env-main-1
echo "宿主时间: $(date '+%H:%M:%S')"
docker ps --format '{{.Names}}|{{.Status}}' | grep "^$C" || { echo "容器未运行"; exit 0; }
docker exec "$C" bash -lc '
  echo "容器时间(UTC): $(date "+%H:%M:%S")"
  echo "--- claude 进程 ---"
  ps -eo pid,etime,pcpu,pmem,cmd 2>/dev/null | grep -E "claude" | grep -v grep | cut -c1-120 | head -5
  echo "--- 最近判分会话目录 ---"
  ls -1dt /tmp/claude-0/-app/*/ 2>/dev/null | head -4 | while read -r d; do
    echo "  $(date -r "$d" "+%H:%M:%S") $(basename "$d" | cut -c1-8)"
  done
  echo "--- 最近写入的文件（全域，排除 proc/sys）---"
  find /tmp /logs /root -type f -newermt "-12 minutes" 2>/dev/null | head -8
  echo "--- 载入与内存 ---"
  uptime; free -m | head -2
' 2>/dev/null
