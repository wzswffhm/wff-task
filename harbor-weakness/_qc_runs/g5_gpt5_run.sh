#!/bin/bash
# G5: gpt-5.6-sol agent 跑分（fanrenapi，anthropic 协议；与 oracle 判分不同 key，可并行）
set -u
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
OUT=$TASK_ROOT/harbor-weakness/_qc_runs/g5-152v2-gpt5
mkdir -p "$OUT/trials"
rm -rf "$OUT/trials"/* 2>/dev/null || true

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a
FANREN_KEY='sk-kD3rBDui7Jj4Z1shaFzoMU5l8xjyrbOU99ij4uHrbvmN3UUE'

export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1

cd "$TASK_ROOT" || exit 90
{
  echo "=== start $(date '+%F %T') ==="
  echo "model: gpt-5.6-sol via fanrenapi (anthropic protocol)"
} > "$OUT/gpt.log"

harbor trial start \
  -p harbor-weakness/FIN3-WKN-152 \
  -a claude-code \
  -m gpt-5.6-sol \
  --trial-name gpt56sol5-152v2 \
  --trials-dir "$OUT/trials" \
  --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
  --ae ANTHROPIC_BASE_URL=https://fanrenapi.com \
  --ae ANTHROPIC_API_KEY="$FANREN_KEY" \
  --ae ANTHROPIC_AUTH_TOKEN="$FANREN_KEY" \
  --ae ANTHROPIC_MODEL=gpt-5.6-sol \
  --ae ANTHROPIC_SMALL_FAST_MODEL=gpt-5.6-sol \
  --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=gpt-5.6-sol \
  --ae CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/gpt.log" 2>&1
rc=$?
echo "EXIT=$rc" >> "$OUT/gpt.log"
echo "=== done $(date '+%F %T') ===" >> "$OUT/gpt.log"
exit $rc
