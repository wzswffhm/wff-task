#!/usr/bin/env bash
# 核实：批次归档的 oracle/output 五图 是否与 WSL 任务目录 golden_output 的图一致
B=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261011_fix9-149/FIN3-WKN-149
W=/home/wff/harbor-tasks-fix8/FIN3-WKN-149
echo "=== 批次归档 oracle/output 图 ==="
for f in "$B/跑分产物与轨迹/oracle/output/FIN3-WKN-149_charts"/*.png; do
  [ -f "$f" ] && echo "  $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
done
echo "=== 批次 solution/golden_output 图（应为修后新图）==="
for f in "$B/solution/golden_output/FIN3-WKN-149_charts"/*.png; do
  [ -f "$f" ] && echo "  $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
done
echo "=== WSL 任务目录 golden_output 图（oracle 运行源）==="
for f in "$W/solution/golden_output/FIN3-WKN-149_charts"/*.png; do
  [ -f "$f" ] && echo "  $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
done
echo "=== Windows 源 harbor-weakness/FIN3-WKN-149 golden 图 ==="
for f in /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-149/solution/golden_output/FIN3-WKN-149_charts/*.png; do
  [ -f "$f" ] && echo "  $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
done
echo ""
echo "=== fix8 旧 oracle 图（_fix8_extract）==="
for f in /mnt/c/Users/Administrator/Desktop/wff-task/deliverables/2026-10-09_harbor-weakness-149-二次返修/_fix8_extract/work_fin-b01_20261009_fix8-149/FIN3-WKN-149/跑分产物与轨迹/oracle/output/FIN3-WKN-149_charts/*.png; do
  [ -f "$f" ] && echo "  $(sha256sum "$f" | cut -c1-16)  $(stat -c%s "$f")  $(basename "$f")"
done
echo ""
echo "=== 当前日期 ==="
date '+%F %T %Z'
