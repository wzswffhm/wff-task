#!/usr/bin/env bash
# Monitor treefiles difficulty gate: record only, NEVER kill (skill: batch must
# complete all 16 trials). Reports infra failures only.
set -u
JOBS_DIR=/home/wff/harbor/block-storage-c-feature-20260813-1515/jobs/tree-difficulty-16c16
LOG=/home/wff/harbor/block-storage-c-feature-20260813-1515/jobs/monitor.log
echo "monitor started (record-only)" > "$LOG"
while true; do
  C=0; TOTAL=0; FAIL=0
  for f in "$JOBS_DIR"/*/*/verifier/reward.txt "$JOBS_DIR"/*/verifier/reward.txt; do
    [ -f "$f" ] || continue
    TOTAL=$((TOTAL+1))
    v=$(tr -d " \n" < "$f")
    if [ "$v" = "1.0" ] || [ "$v" = "1" ]; then C=$((C+1)); fi
  done
  FAIL=$(find "$JOBS_DIR" -name exception.txt 2>/dev/null | wc -l)
  echo "$(date +%H:%M:%S) reward1=$C completed=$TOTAL exceptions=$FAIL" >> "$LOG"
  ALIVE=$(ps aux | grep -E "harbor (run|job)" | grep -v grep | wc -l)
  if [ "$ALIVE" -eq 0 ] && [ "$TOTAL" -ge 1 ]; then
    echo "$(date +%H:%M:%S) harbor finished, final: reward1=$C completed=$TOTAL" >> "$LOG"
    exit 0
  fi
  sleep 60
done
