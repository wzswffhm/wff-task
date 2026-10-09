#!/bin/bash
# G5: qwen3.8-max-0902 agent 跑分（阿里云网关，anthropic 协议）
# 注意：与 oracle 判分共用同一 JUDGE_API_KEY，须在 oracle 判分结束后再启动，避免同 key 互相拖死。
set -u
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
OUT=$TASK_ROOT/harbor-weakness/_qc_runs/g5-152v2-qwen2
mkdir -p "$OUT/trials"
rm -rf "$OUT/trials"/* 2>/dev/null || true

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1

cd "$TASK_ROOT" || exit 90
{
  echo "=== start $(date '+%F %T') ==="
  echo "model: qwen3.8-max-0902 via gateway (anthropic protocol)"
} > "$OUT/qwen.log"

harbor trial start \
  -p harbor-weakness/FIN3-WKN-152 \
  -a claude-code \
  -m qwen3.8-max-0902 \
  --trial-name qwen38max2-152v2 \
  --trials-dir "$OUT/trials" \
  --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
  --ae ANTHROPIC_BASE_URL="$JUDGE_BASE_URL" \
  --ae ANTHROPIC_API_KEY="$JUDGE_API_KEY" \
  --ae ANTHROPIC_AUTH_TOKEN="$JUDGE_API_KEY" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/qwen.log" 2>&1
rc=$?
echo "EXIT=$rc" >> "$OUT/qwen.log"
echo "=== done $(date '+%F %T') ===" >> "$OUT/qwen.log"
exit $rc
