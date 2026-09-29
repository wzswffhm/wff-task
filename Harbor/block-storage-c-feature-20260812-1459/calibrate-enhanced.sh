#!/usr/bin/env bash
# Calibrate baseline + oracle for the enhanced 8-scenario suite.
set -u
export PATH=/home/wff/.local/bin:/usr/bin:/bin
KEY=$(grep -o "sk-ws-[A-Za-z0-9._-]*" /tmp/launch-cow.sh | head -1)
BASE="https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
cd /home/wff/harbor
TASK=block-storage-c-feature-20260812-1459

echo "===== BASELINE (nop) ====="
rm -rf "$TASK/jobs/baseline"
mkdir -p "$TASK/jobs/baseline"
printf 'Y\n' | harbor trials start -p $TASK --agent nop --trials-dir $TASK/jobs/baseline \
  --ae OPENAI_API_KEY=$KEY --ae OPENAI_BASE_URL=$BASE \
  --ve ANTHROPIC_API_KEY=$KEY --ve OPENAI_API_KEY=$KEY --ve DASHSCOPE_API_KEY=$KEY 2>&1 | tail -6
echo "baseline exit=$?"

echo "===== ORACLE (patch applied) ====="
rm -rf "$TASK/jobs/oracle"
mkdir -p "$TASK/jobs/oracle"
printf 'Y\n' | harbor trials start -p $TASK --agent oracle --trials-dir $TASK/jobs/oracle \
  --ae OPENAI_API_KEY=$KEY --ae OPENAI_BASE_URL=$BASE \
  --ve ANTHROPIC_API_KEY=$KEY --ve OPENAI_API_KEY=$KEY --ve DASHSCOPE_API_KEY=$KEY 2>&1 | tail -6
echo "oracle exit=$?"
