#!/usr/bin/env bash
# Launch batch 2 of treefiles difficulty gate (same frozen revision, reuse image).
set -u
export PATH=/home/wff/.local/bin:/usr/bin:/bin:/usr/local/bin
KEY=$(grep -o "sk-ws-[A-Za-z0-9._-]*" /tmp/launch-cow.sh | head -1)
BASE="https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
cd /home/wff/harbor
TASK=block-storage-c-feature-20260813-1515
JOBS_DIR="$TASK/jobs/tree-difficulty-16c16-b2"
rm -rf "$JOBS_DIR"
mkdir -p "$JOBS_DIR"

setsid bash -c "printf 'Y\n' | harbor run \
  --path $TASK/ \
  --agent qwen-coder --model qwen3.8-max \
  --ae OPENAI_API_KEY='$KEY' \
  --ae OPENAI_BASE_URL='$BASE' \
  --ve ANTHROPIC_API_KEY='$KEY' \
  --ve OPENAI_API_KEY='$KEY' \
  --ve DASHSCOPE_API_KEY='$KEY' \
  --n-attempts 16 --n-concurrent 16 --n-concurrent-agents 16 --max-retries 3 \
  --agent-setup-timeout-multiplier 3 \
  --no-force-build \
  --job-name tree-difficulty-16c16-b2 \
  --jobs-dir $JOBS_DIR \
  --yes" > /tmp/tree_difficulty_b2.log 2>&1 < /dev/null &
echo "batch-2 16-concurrent launched"
