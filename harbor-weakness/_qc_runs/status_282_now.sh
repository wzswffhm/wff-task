#!/bin/bash
# 282 / FIN3-WKN-152 v3 当前是否在跑 + 各 trial 实况
echo "=== services ==="
for s in g4-152v3 g5-v3-qwen g5-v3-gpt g5-v3-opus; do
  printf '  %-14s %s\n' "$s" "$(systemctl is-active $s.service 2>/dev/null)"
done
echo "=== 容器 ==="
docker ps --format '  {{.Names}} | {{.Status}}'
echo "=== _qc_runs 下 v3 trial 目录 ==="
ls -d /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/*152v3* 2>/dev/null | sed 's/^/  /'
echo "=== 各 reward.json ==="
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
for d in g4-152v3 g5-152v3-qwen g5-152v3-gpt g5-152v3-opus; do
  f=$(find "$Q/$d/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    echo -n "  $d: "; tr -d '\n' < "$f"; echo
  else
    echo "  $d: (无 reward.json)"
  fi
done
date '+%F %T'
