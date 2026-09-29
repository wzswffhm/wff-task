#!/usr/bin/env bash
# Pool candidates from batch1 (complete) + batch2 (completed so far).
# Duplicate check: md5 of agent session + trajectory + workspace diff markers.
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
B1="$TASK/jobs/tree-difficulty-16c16/tree-difficulty-16c16"
B2="$TASK/jobs/tree-difficulty-16c16-b2/tree-difficulty-16c16-b2"
POOL=/tmp/tree_pool.txt
> "$POOL"

for JOB in "$B1" "$B2"; do
  for d in "$JOB"/*/; do
    rw="$d/verifier/reward.txt"
    [ -f "$rw" ] || continue
    r=$(tr -d ' \n' < "$rw")
    n=$(basename "$d")
    src=$(echo "$JOB" | grep -o "tree-difficulty-16c16[^/]*")
    sess="$d/agent/qwen-code.txt"
    traj="$d/agent/trajectory.json"
    smd="NA"; tmd="NA"; sbytes="NA"
    if [ -f "$sess" ]; then smd=$(md5sum "$sess" | cut -c1-12); sbytes=$(wc -c < "$sess"); fi
    if [ -f "$traj" ]; then tmd=$(md5sum "$traj" | cut -c1-12); fi
    echo "$r|$src|$n|$smd|$tmd|$sbytes" >> "$POOL"
  done
done

echo "=== 候选池($(wc -l < "$POOL") 条)==="
echo "reward1=$(grep -c "^1.0|" "$POOL") reward0=$(grep -c "^0.0|" "$POOL")"
echo "=== 会话 md5 重复检测 ==="
awk -F'|' '$4!="NA"{print $4}' "$POOL" | sort | uniq -c | sort -rn | awk '$1>1{print "DUP("$1"): "$2}'
echo "(无输出=无重复)"
echo "=== 轨迹 md5 重复检测 ==="
awk -F'|' '$5!="NA"{print $5}' "$POOL" | sort | uniq -c | sort -rn | awk '$1>1{print "DUP("$1"): "$2}'
echo "(无输出=无重复)"
echo "=== 明细 ==="
cat "$POOL"
