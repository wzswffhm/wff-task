#!/usr/bin/env bash
# busybox unzip 交叉验证（busybox find 不支持 -printf，改用 stat）
set -u
H=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness
docker run --rm -v "$H:/z:ro" alpine:3.20 sh -c '
set -e
for z in work_fin-b01_20261011_fix11-149.zip FIN3-WKN-149_task.zip FIN3-WKN-149_answer.zip work_fin-b01_20261011_fix10-149.zip; do
  rm -rf /t; mkdir -p /t; cd /t
  busybox unzip -q "/z/$z" 2>/dev/null || unzip -q "/z/$z"
  echo "--- $z"
  for f in $(busybox find /t -name "*.sh" | sort); do
    echo "    $(busybox stat -c "%a" "$f")  $(basename $f)"
  done
  d=$(busybox find /t -mindepth 1 -maxdepth 1 -type d | head -1)
  echo "    (目录) $(busybox stat -c "%a" "$d")"
  m=$(busybox find /t -name "*.md" | head -1)
  echo "    (普通文件) $(busybox stat -c "%a" "$m")"
done
' 2>&1
