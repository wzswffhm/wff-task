#!/bin/bash

# --- WSL 出站必须走 Windows 侧 pproxy（本环境无直连 TCP）---
GW=$(ip route 2>/dev/null | awk "/^default/{print \$3; exit}")
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  export no_proxy="localhost,127.0.0.1,::1"
fi
unset GW
# --- end proxy ---
# G5 v4: claude-opus-4-8 在 FIN3-WKN-152 v4.0.0 上跑分（4router 端点，anthropic 协议）
set -u
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a   # JUDGE_*（verifier 用）

export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

OPUS_BASE=https://4router.net
OPUS_KEY=sk-ABTdFUULEu52VnGHNhWQX8BA13uMpbPdTZZrogR5oGTla2gE

OUT=$Q/g5-152v4-opus
mkdir -p "$OUT/trials"; rm -rf "$OUT/trials"/* 2>/dev/null || true
echo "=== start $(date '+%F %T') opus (4router) ===" > "$OUT/opus.log"
harbor trial start \
  -p harbor-weakness/FIN3-WKN-152 -a claude-code -m claude-opus-4-8 \
  --trial-name opus48-152v4 --trials-dir "$OUT/trials" \
  --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
  --ae ANTHROPIC_BASE_URL="$OPUS_BASE" \
  --ae ANTHROPIC_API_KEY="$OPUS_KEY" \
  --ae ANTHROPIC_AUTH_TOKEN="$OPUS_KEY" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/opus.log" 2>&1
echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/opus.log"
