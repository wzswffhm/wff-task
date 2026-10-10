#!/bin/bash
# 统一重判（regrade）：对已完成 trial 用同一判据/判官重跑 verifier，消除单条判官噪声
# 用法: bash unified_regrade.sh <qwen|gpt|opus>
set -u
WHICH="${1:?用法: unified_regrade.sh <qwen|gpt|opus>}"
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT" no_proxy="localhost,127.0.0.1"

TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs

# 源 trial / 输出目录 / 新 trial 名
case "$WHICH" in
  qwen) SRC=$Q/g5-152v4-qwen/trials/qwen38max-152v4
        OUT=$Q/g5-152v4-qwen/reg            NEW=qwen38max-152v4-reg1 ;;
  gpt)  SRC=$Q/g5-152v4-gpt/trials/gpt56sol-152v4
        OUT=$Q/g5-152v4-gpt/reg             NEW=gpt56sol-152v4-reg1 ;;
  opus) SRC=$Q/g5-152v4-opus/trials/opus48-152v4
        OUT=$Q/g5-152v4-opus/reg            NEW=opus48-152v4-reg1 ;;
  *) echo "未知: $WHICH"; exit 2 ;;
esac

# 判官凭据
CREDS=/mnt/c/Users/Administrator/.wff-creds
set -a; . "$CREDS/judge.env"; set +a

export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

if [ ! -d "$SRC" ]; then
  echo "[!!] 源 trial 不存在: $SRC"
  exit 3
fi
mkdir -p "$OUT"
LOG=$OUT/$WHICH-regrade.log
echo "=== regrade $WHICH  源=$SRC  新trial=$NEW ===" | tee "$LOG"
echo "开始: $(date '+%F %T')" | tee -a "$LOG"

harbor trial regrade "$SRC" \
  -p harbor-weakness/FIN3-WKN-152 \
  --trial-name "$NEW" \
  --trials-dir "$OUT" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$LOG" 2>&1
rc=$?
echo "EXIT=$rc  结束: $(date '+%F %T')" | tee -a "$LOG"
echo "日志: $LOG"
exit $rc
