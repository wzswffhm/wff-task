#!/usr/bin/env bash
# 把 fix8 批次包预置为 fix9 工作批次（复制解压产物到工作区，准备归档覆盖跑分产物）
set -e
SRC="/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/2026-10-09_harbor-weakness-149-二次返修/_fix8_extract"
DST="/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261009_fix8-149"
echo "=== 源批次结构 ==="
find "$SRC" -maxdepth 3 -type d | head -20
echo "=== 目标批次（当前残留）==="
find "$DST" -maxdepth 3 -type d 2>/dev/null | head -20
echo "=== 清空目标，从源重建 ==="
rm -rf "$DST"
mkdir -p "$DST"
cp -r "$SRC/work_fin-b01_20261009_fix8-149/." "$DST/"
echo "=== 重建后 ==="
find "$DST" -maxdepth 3 -type d | head -20
echo "=== 关键文件 ==="
ls -la "$DST/FIN3-WKN-149/" | head -20
