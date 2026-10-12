#!/usr/bin/env bash
# 端到端：把飞书下载件复制到 ASCII 路径，用真实解压器复验解压后权限
set -u
SRC="/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/2026-10-09_harbor-weakness-149-二次返修/_feishu_verify_fix11"
WORK=/tmp/e2e_fix11
rm -rf "$WORK"; mkdir -p "$WORK"
i=0
for f in "$SRC"/*.zip; do
  [ -f "$f" ] || continue
  i=$((i+1))
  cp "$f" "$WORK/z$i.zip"
  echo "z$i.zip <= $(basename "$f")"
done
ls -la "$WORK"

echo ""
echo "############ busybox unzip（alpine:3.20） ############"
docker run --rm -v "$WORK:/z:ro" alpine:3.20 sh -c '
for z in /z/*.zip; do
  rm -rf /t; mkdir -p /t; cd /t
  busybox unzip -q "$z" >/dev/null 2>&1
  echo "--- $(basename $z)"
  busybox find /t -name "*.sh" -exec busybox stat -c "    %a  %n" {} \; | sort
done
'

echo ""
echo "############ Info-ZIP unzip（fin3-wkn-149:local） ############"
docker run --rm -v "$WORK:/z:ro" --entrypoint sh fin3-wkn-149:local -c '
for z in /z/*.zip; do
  rm -rf /t; mkdir -p /t; cd /t
  unzip -oq "$z" >/dev/null 2>&1
  echo "--- $(basename $z)"
  find /t -name "*.sh" -printf "    %m  %p\n" | sed "s|/t/||" | sort
done
'
