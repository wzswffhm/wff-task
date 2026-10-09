#!/bin/bash
# G5 v3: 双模型（qwen3.8-max-0902 + gpt-5.6-sol）在 FIN3-WKN-152 v3.0.0 上跑分。
# qwen = 阿里云网关(anthropic 协议)；gpt = fanrenapi(anthropic 协议，BASE_URL 不带 /v1)。
# 与 G4 oracle 共用同一 JUDGE_API_KEY，须在 oracle 判分结束后再启动。
set -u
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a   # 提供 JUDGE_* 与 JUDGE_API_KEY（qwen 走同一 key）

export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

# fanrenapi key（gpt 用，不带 /v1）
GPT_BASE=https://fanrenapi.com
GPT_KEY=$(grep -oE 'sk-[A-Za-z0-9]+' /mnt/c/Users/Administrator/.wff-creds/fanrenapi.key 2>/dev/null | head -1)
if [ -z "${GPT_KEY:-}" ]; then GPT_KEY=sk-kD3rBDui7Jj4Z1shaFzoMU5l8xjyrbOU99ij4uHrbvmN3UUE; fi

which_model="$1:-"

run_qwen() {
  OUT=$Q/g5-152v3-qwen
  mkdir -p "$OUT/trials"; rm -rf "$OUT/trials"/* 2>/dev/null || true
  echo "=== start $(date '+%F %T') qwen ===" > "$OUT/qwen.log"
  harbor trial start \
    -p harbor-weakness/FIN3-WKN-152 -a claude-code -m qwen3.8-max-0902 \
    --trial-name qwen38max-152v3 --trials-dir "$OUT/trials" \
    --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
    --ae ANTHROPIC_BASE_URL="$JUDGE_BASE_URL" \
    --ae ANTHROPIC_API_KEY="$JUDGE_API_KEY" \
    --ae ANTHROPIC_AUTH_TOKEN="$JUDGE_API_KEY" \
    --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
    --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
    --ve JUDGE_MODEL="$JUDGE_MODEL" \
    --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
    --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/qwen.log" 2>&1
  echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/qwen.log"
}

run_gpt() {
  OUT=$Q/g5-152v3-gpt
  mkdir -p "$OUT/trials"; rm -rf "$OUT/trials"/* 2>/dev/null || true
  echo "=== start $(date '+%F %T') gpt ===" > "$OUT/gpt.log"
  harbor trial start \
    -p harbor-weakness/FIN3-WKN-152 -a claude-code -m gpt-5.6-sol \
    --trial-name gpt56sol-152v3 --trials-dir "$OUT/trials" \
    --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
    --ae ANTHROPIC_BASE_URL="$GPT_BASE" \
    --ae ANTHROPIC_API_KEY="$GPT_KEY" \
    --ae ANTHROPIC_AUTH_TOKEN="$GPT_KEY" \
    --ae ANTHROPIC_MODEL=gpt-5.6-sol \
    --ae ANTHROPIC_SMALL_FAST_MODEL=gpt-5.6-sol \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=gpt-5.6-sol \
    --ae CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
    --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
    --ve JUDGE_MODEL="$JUDGE_MODEL" \
    --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
    --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/gpt.log" 2>&1
  echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/gpt.log"
}

case "${1:-both}" in
  qwen) run_qwen ;;
  gpt)  run_gpt ;;
  both) run_qwen; run_gpt ;;
esac
