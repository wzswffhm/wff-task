#!/usr/bin/env bash
# Launch COW difficulty gate (16 attempts, 4 concurrent) + self-scoped monitor.
# Job name cow-difficulty-16c4 keeps pkill self-scoped.
set -u
export PATH=/home/wff/.local/bin:/usr/bin:/bin:/usr/local/bin
export OPENAI_API_KEY="__API_KEY__"
export OPENAI_BASE_URL="https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
export ANTHROPIC_API_KEY="$OPENAI_API_KEY"
export DASHSCOPE_API_KEY="$OPENAI_API_KEY"

cd /home/wff/harbor

TASK_DIR="block-storage-c-feature-20260812-1459"
JOBS_DIR="$TASK_DIR/jobs/difficulty-16c4"
rm -rf "$JOBS_DIR"

setsid bash -c "printf 'Y\n' | harbor run \
  --path $TASK_DIR/ \
  --agent qwen-coder --model qwen3.8-max \
  --ae OPENAI_API_KEY='$OPENAI_API_KEY' \
  --ae OPENAI_BASE_URL='$OPENAI_BASE_URL' \
  --n-attempts 16 --n-concurrent 4 --max-retries 3 \
  --agent-timeout-multiplier 10 --agent-setup-timeout-multiplier 5 \
  --job-name cow-difficulty-16c4 \
  --jobs-dir $JOBS_DIR \
  --yes" > /tmp/cow_difficulty.log 2>&1 < /dev/null &
echo "harbor launched"

setsid bash -c "bash /home/wff/harbor/scripts/monitor-cow-difficulty.sh $JOBS_DIR" > /tmp/cow_monitor.log 2>&1 < /dev/null &
echo "monitor launched"
