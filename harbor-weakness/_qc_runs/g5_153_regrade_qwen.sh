#!/bin/bash
# 串联收尾：等 gpt / opus 两个执行体结束后，对 qwen 执行体做「仅重判」（复用其 agent 产物）。
# 首轮 qwen 判分失败原因为 judge:scorer_error（socket connection was closed unexpectedly），
# 属网关瞬时故障，非题包缺陷；重判不重跑 agent，节省时间。
set -u

GW=$(ip route 2>/dev/null | sed -n 's/^default via \([0-9.]*\).*/\1/p')
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  export no_proxy="localhost,127.0.0.1,::1"
fi

TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_PATH=harbor-weakness/work_fin-b01_20261012-153/FIN3-WKN-153

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

LOG=$Q/g5-153-qwen/regrade.log
SRC=$Q/g5-153-qwen/trials/qwen38max-153
OUT=$Q/g5-153-qwen/trials
NEW=qwen38max-153-reg1

echo "=== wait gpt/opus $(date '+%F %T') ===" > "$LOG"
for _i in $(seq 1 300); do
  g=0; o=0
  grep -q '^EXIT=' "$Q/g5-153-gpt/gpt.log" 2>/dev/null && g=1
  grep -q '^EXIT=' "$Q/g5-153-opus/opus.log" 2>/dev/null && o=1
  [ "$g" -eq 1 ] && [ "$o" -eq 1 ] && break
  sleep 60
done
echo "gpt=$g opus=$o 开始重判 $(date '+%F %T')" >> "$LOG"

if [ ! -d "$SRC" ]; then
  echo "[!!] 源 trial 缺失: $SRC" >> "$LOG"
  exit 3
fi

harbor trial regrade "$SRC" \
  -p "$TASK_PATH" \
  --trial-name "$NEW" \
  --trials-dir "$OUT" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$LOG" 2>&1
echo "EXIT=$? done $(date '+%F %T')" >> "$LOG"
