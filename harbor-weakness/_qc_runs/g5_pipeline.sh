#!/bin/bash
# G5 流水线：等 oracle 判分结束 → 跑 qwen3.8-max-0902（避免与 oracle 同 key 并发）→ 等 gpt-5.6-sol 结束。
set -u
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
RUNS=$TASK_ROOT/harbor-weakness/_qc_runs
LOG=$RUNS/g5_pipeline.log

echo "=== pipeline start $(date '+%F %T') ===" > "$LOG"

# 1) 等 oracle 判分完成
for i in $(seq 1 600); do
  if ! systemctl is-active --quiet g4-152v2; then break; fi
  echo "[$(date '+%T')] waiting oracle ..." >> "$LOG"
  sleep 60
done
echo "[$(date '+%T')] oracle unit inactive" >> "$LOG"

# 2) qwen3.8-max-0902（前台，agent + 判分）
bash "$RUNS/g5_qwen_run.sh" >> "$LOG" 2>&1
echo "[$(date '+%T')] qwen script exited rc=$?" >> "$LOG"

# 3) 等 gpt-5.6-sol 完成
for i in $(seq 1 600); do
  if ! systemctl is-active --quiet g5-gpt-152v2; then break; fi
  echo "[$(date '+%T')] waiting gpt ..." >> "$LOG"
  sleep 60
done
echo "[$(date '+%T')] gpt unit inactive" >> "$LOG"
echo "=== pipeline done $(date '+%F %T') ===" >> "$LOG"
