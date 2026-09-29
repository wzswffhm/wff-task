#!/usr/bin/env bash
# Baseline calibration for block-storage-c-feature-20260812-1459.
# Runs 1 trial with the nop agent (agent does nothing) => expect reward=0.
set -u
export PATH=/home/wff/.local/bin:/usr/bin:/bin:/usr/local/bin
source ~/.bashrc >/dev/null 2>&1 || true
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1}"
export ANTHROPIC_API_KEY="$OPENAI_API_KEY"
export DASHSCOPE_API_KEY="$OPENAI_API_KEY"
export ANTHROPIC_API_BASE="https://dashscope.aliyuncs.com/apps/anthropic"

cd /home/wff/harbor

TASK_DIR="block-storage-c-feature-20260812-1459"
JOBS_DIR="$TASK_DIR/jobs/baseline"
rm -rf "$JOBS_DIR"
mkdir -p "$JOBS_DIR"

printf 'Y\n' | harbor trials start \
  --path "$TASK_DIR" \
  --agent nop \
  --trials-dir "$JOBS_DIR" \
  --yes > "$JOBS_DIR/trials.log" 2>&1
echo "baseline exit: $?"
tail -20 "$JOBS_DIR/trials.log"
