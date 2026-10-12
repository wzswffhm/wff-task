#!/bin/bash
# 收尾看守（2026-10-12 甲方指示 opus 端点有问题，暂不跑）：
#   1) 若 opus 执行体被串行调度启动，立即终止它；
#   2) 等 gpt 执行体结束；
#   3) 对 qwen 执行体做「仅重判」（复用 agent 产物；首轮失败原因为网关 socket 断连）。
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
LOG=$Q/watchdog_153b.log

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

echo "=== watchdog-b start $(date '+%F %T')（opus 暂停）===" > "$LOG"

for _i in $(seq 1 300); do
  # ① 发现 opus 执行体被调度则终止（甲方指示暂不跑）
  opus_pids=$(pgrep -f 'opus48-153' 2>/dev/null || true)
  if [ -n "$opus_pids" ]; then
    for p in $opus_pids; do
      pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
      [ -n "${pgid:-}" ] && kill -TERM "-$pgid" 2>/dev/null
    done
    sleep 2
    for p in $opus_pids; do
      pgid=$(ps -o pgid= -p "$p" 2>/dev/null | tr -d ' ')
      [ -n "${pgid:-}" ] && kill -KILL "-$pgid" 2>/dev/null
    done
    for c in $(docker ps -a --format '{{.Names}}' | grep 'opus48-153'); do docker rm -f "$c" >/dev/null 2>&1; done
    echo "[$(date '+%F %T')] opus 执行体已按指示终止：$opus_pids" >> "$LOG"
  fi
  # ② gpt 结束即退出等待
  if grep -q '^EXIT=' "$Q/g5-153-gpt/gpt.log" 2>/dev/null; then
    echo "[$(date '+%F %T')] gpt 已结束" >> "$LOG"
    break
  fi
  sleep 45
done

# ③ qwen 仅重判
SRC=$Q/g5-153-qwen/trials/qwen38max-153
OUT=$Q/g5-153-qwen/trials
NEW=qwen38max-153-reg1
if [ ! -d "$SRC" ]; then
  echo "[!!] 源 trial 缺失: $SRC" >> "$LOG"
  exit 3
fi
echo "[$(date '+%F %T')] 开始 qwen 重判 -> $NEW" >> "$LOG"
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
