#!/bin/bash
# FIN3-WKN-153 qwen「verifier-only 重判」（2026-10-12）
#
# 背景：第 4 次完整 trial 的 agent 段成功（6 件交付物齐备、terminal_reason=completed），
# 但判官凭据被平台封禁 —— ~/.wff-creds/judge.env 的 JUDGE_API_KEY（尾号 oZ5EMs）
# 直测返回 401 {"code":"InvalidApiKey","message":"API-key is blocked."}，
# 对 qwen3.7-plus 与 qwen3.8-max-0902 均如此（非限流，是 key 被封）。
# 用户 2026-10-12 确认改用 models.local.json 中 qwen 端点那把 key（直测两个模型均 200）。
#
# 做法（依据 delivery/06-model-validation.md §"复用已记录的交付物重判"）：
#   - 本题 verifier 为 shared 模式，`harbor trial regrade` 不适用 →
#     等价路径 `-a nop` + bind mount 把该模型真实交付物塞进容器 /app/output，只跑真判分；
#   - 不重跑 agent（省约 50 分钟与约 7.4 USD）；
#   - 判官模型/协议口径不变（仍是 qwen3.7-plus / anthropic），仅更换被封的 key。
#
# 用法: setsid nohup bash g5_153_regrade_qwen_v2.sh &
set -u

# docker compose(2.40) 默认走 Bake，本机无 buildx 会直接构建失败（见 g5_153_run.sh 同款注释）
export COMPOSE_BAKE=false

TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs
TASK_PATH=harbor-weakness/work_fin-b01_20261012-153/FIN3-WKN-153
SRC=$Q/g5-153-qwen/_reuse_r4/output
OUT=$Q/g5-153-qwen/trials
LOG=$Q/g5-153-qwen/regrade_v2.log

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

# 判官凭据：取自 models.local.json 的 qwen 端点（用户 2026-10-12 指定）
eval "$(python3 - "$TASK_ROOT/models.local.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
ep = next(x for x in data["endpoints"] if x["key"] == "qwen3.8-max")
print(f"BASE={ep['base_url']!r}")
print(f"KEY={ep['api_key']!r}")
PY
)"

[ -f "$SRC/FIN3-WKN-153_operation_report.md" ] || { echo "[!!] 复用交付物缺失: $SRC"; exit 3; }

{
  echo "=== start $(date '+%F %T') qwen verifier-only regrade ==="
  echo "src=$SRC （$(ls -1 "$SRC" | wc -l) 件交付物）"
  echo "judge_model=qwen3.7-plus judge_base=$BASE"
} > "$LOG"

harbor trial start -p "$TASK_PATH" -a nop \
  --trial-name qwen38max-153-reg1 \
  --trials-dir "$OUT" \
  --mounts "[{\"type\":\"bind\",\"source\":\"$SRC\",\"target\":\"/app/output\"}]" \
  --ve JUDGE_API_KEY="$KEY" \
  --ve JUDGE_BASE_URL="$BASE" \
  --ve JUDGE_MODEL=qwen3.7-plus \
  --ve JUDGE_PROVIDER=anthropic \
  --ve JUDGE_API_PROTOCOL=anthropic >> "$LOG" 2>&1
echo "EXIT=$? done $(date '+%F %T')" >> "$LOG"
