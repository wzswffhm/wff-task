#!/bin/bash
# SOTA 跑分封装：按模型自动切换 shuaiapi key，裁判固定 gpt-5.5
# 用法: scripts/sota-run.sh <task_dir> <model> [额外 harbor run 参数...]
# 模型: claude-opus-4-8 | glm-5.2 | kimi-k3
set -euo pipefail

if [ -z "${SOTA_BASE_URL:-}" ]; then
  # shellcheck disable=SC1090
  . ~/.sota.env
fi

TASK="${1:?用法: sota-run.sh <task_dir> <model> [额外参数...]}"
MODEL="${2:?缺少模型名}"
shift 2

case "$MODEL" in
  claude-opus-4-8)
    AKEY="$SOTA_KEY_CLAUDE"
    ;;
  glm-5.2|kimi-k3)
    AKEY="$SOTA_KEY_GLM_KIMI"
    ;;
  *)
    echo "未知模型: $MODEL（支持: claude-opus-4-8 / glm-5.2 / kimi-k3）" >&2
    exit 1
    ;;
esac

echo ">>> 待测模型: $MODEL | 裁判: gpt-5.5"
echo ">>> 命令: harbor run --path $TASK --agent claude-code --model $MODEL $*"

harbor run \
  --path "$TASK" \
  --agent claude-code \
  --model "$MODEL" \
  --ae "ANTHROPIC_API_KEY=$AKEY" \
  --ae "ANTHROPIC_BASE_URL=$SOTA_BASE_URL" \
  --ve "OPENAI_API_KEY=$SOTA_KEY_JUDGE_GPT" \
  --ve "OPENAI_BASE_URL=$SOTA_BASE_URL" \
  "$@"
