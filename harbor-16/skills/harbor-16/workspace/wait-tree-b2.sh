#!/usr/bin/env bash
# Wait for batch 2 (tree-difficulty-16c16-b2) to finish, then summarize.
set -u
JOB=/home/wff/harbor/block-storage-c-feature-20260813-1515/jobs/tree-difficulty-16c16-b2
while true; do
  TOTAL=0; R1=0
  for f in "$JOB"/*/*/verifier/reward.txt "$JOB"/*/verifier/reward.txt; do
    [ -f "$f" ] || continue
    TOTAL=$((TOTAL+1))
    v=$(tr -d " \n" < "$f")
    if [ "$v" = "1.0" ] || [ "$v" = "1" ]; then R1=$((R1+1)); fi
  done
  ALIVE=$(ps aux | grep -E "harbor (run|job)" | grep -v grep | wc -l)
  if [ "$ALIVE" -eq 0 ] && [ "$TOTAL" -ge 1 ]; then
    echo "BATCH2 DONE: completed=$TOTAL reward1=$R1"
    for d in "$JOB"/*/; do
      r=$(cat "$d/verifier/reward.txt" 2>/dev/null | tr -d ' \n')
      [ -n "$r" ] && echo "$(basename "$d"): reward=$r"
    done
    exit 0
  fi
  sleep 90
done
