#!/bin/bash
# FIN3-WKN-153 G5 opus「verifier-only 重判」（2026-10-12）
#
# 背景：opus 完整 trial（opus48-153，21:38 启动）agent 段**成功**（6 件交付物齐备、全程无 403），
# 判分推进至 **28/34** 条后，第 29 条判官陷入 A11 型空转：它已给出该条结构化评分，却被反复提示
# “上次输出未使用工具调用”，于是反复执行 `Bash: echo "Complete"`，会话文件仍以 ~16 KB/25 s 增长
# 而 StructuredOutput 停在 13 —— 判定不可自愈，22:46 终止（harbor EXIT=143），
# 该 trial 的 reward.json 为 fail-closed 占位（criteria_counted=0 / verifier_error=1），**不是 0 分**。
#
# 处置（依据 delivery/06-model-validation.md §"复用已记录的交付物重判"）：
#   本题 verifier 为 shared 模式，`harbor trial regrade` 不适用 →
#   等价路径 `-a nop` + bind mount 把该模型真实交付物挂到容器 /app/output，只跑真判分；
#   跳过 agent 段（省约 15 分钟），判官模型与协议不变（qwen3.7-plus / anthropic / individual / 7200s）。
#
# 用法: setsid nohup bash g5_153_regrade_opus_v2.sh &
set -u

export COMPOSE_BAKE=false

TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs
CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_PATH=harbor-weakness/work_fin-b01_20261012-153/FIN3-WKN-153
SRC=$Q/g5-153-opus/_reuse_opus/output
OUT=$Q/g5-153-opus/trials
LOG=$Q/g5-153-opus/regrade_v2.log

# 判官凭据：judge.env（2026-10-12 已把被封的旧 key 备份并换为直测可用的 key）
# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

[ -f "$SRC/FIN3-WKN-153_operation_report.md" ] || { echo "[!!] 复用交付物缺失: $SRC"; exit 3; }

{
  echo "=== start $(date '+%F %T') opus verifier-only regrade ==="
  echo "src=$SRC （$(ls -1 "$SRC" | wc -l) 件交付物）"
  echo "judge_model=$JUDGE_MODEL judge_base=$JUDGE_BASE_URL"
} > "$LOG"

harbor trial start -p "$TASK_PATH" -a nop \
  --trial-name opus48-153-reg1 \
  --trials-dir "$OUT" \
  --mounts "[{\"type\":\"bind\",\"source\":\"$SRC\",\"target\":\"/app/output\"}]" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$LOG" 2>&1
echo "EXIT=$? done $(date '+%F %T')" >> "$LOG"
