#!/bin/bash
# G5 三模型难度验证（FIN3-WKN-153）
# 端点来源：仓库根 models.local.json（2026-10-12 起统一端点文件，已纳入版本控制）
#   qwen3.8-max  → 阿里云 MaaS（Anthropic 兼容）
#   gpt-5.6-sol  → fanrenapi（base_url 带 /v1，接入 claude-code 时剥除）
#   opus-5       → 4router.net（模型名按 149–152 口径传 claude-opus-4-8）
# 判官凭据：~/.wff-creds/judge.env（JUDGE_MODEL=qwen3.7-plus）
# 用法: setsid nohup bash g5_153_run.sh <qwen|gpt|opus|all> &
set -u

GW=$(ip route 2>/dev/null | sed -n 's/^default via \([0-9.]*\).*/\1/p')
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  # 2026-10-12：4router（opus-5）与阿里云 MaaS 均须直连——经 :18080 代理会超时，
  # 故把这些域名排除在代理之外（容器内流量不受此处影响）。
  export no_proxy="localhost,127.0.0.1,::1,4router.net,.4router.net,llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com,.aliyuncs.com,fanrenapi.com,.fanrenapi.com"
fi

# 2026-10-12：本机 docker compose（2.40.3）默认用 Bake 构建，但 docker 未装 buildx 插件
# （且 ~/.docker/buildx/current 曾被 root 占用、报 permission denied），
# 会使 `docker compose build` 直接失败、trial 秒退（EXIT=0 + RuntimeError）。
# 固定关闭 Bake，回退传统 builder。
export COMPOSE_BAKE=false

TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
Q=$TASK_ROOT/harbor-weakness/_qc_runs
CREDS=/mnt/c/Users/Administrator/.wff-creds
MODELS_JSON=$TASK_ROOT/models.local.json
TASK_PATH=harbor-weakness/work_fin-b01_20261012-153/FIN3-WKN-153

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

# --- 从 models.local.json 解析端点（base_url 去尾部 /v1，交由 CLI 拼接）---
ENVFILE=/tmp/g5_153_endpoints.env
python3 - "$MODELS_JSON" > "$ENVFILE" <<'PY'
import json
import sys

want = {"qwen3.8-max": "QWEN", "gpt-5.6-sol": "GPT", "opus-5": "OPUS"}
with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)
found = {}
for e in data.get("endpoints", []):
    tag = want.get(e.get("key"))
    if not tag:
        continue
    base = (e.get("base_url") or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    key = e.get("api_key") or ""
    model = e.get("model") or ""
    print(f"export {tag}_BASE='{base}'")
    print(f"export {tag}_KEY='{key}'")
    print(f"export {tag}_MODEL='{model}'")
    found[tag] = bool(base and key)
print("export ENDPOINTS_OK='%s'" % ("1" if all(found.get(t) for t in want.values()) else "0"))
PY
# shellcheck disable=SC1090
. "$ENVFILE"
echo "endpoints: qwen=${QWEN_BASE:-none} gpt=${GPT_BASE:-none} opus=${OPUS_BASE:-none} ok=${ENDPOINTS_OK:-0}"

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1
cd "$TASK_ROOT" || exit 90

common_ve() {
  printf -- '--ve JUDGE_API_KEY=%s --ve JUDGE_BASE_URL=%s --ve JUDGE_MODEL=%s --ve JUDGE_PROVIDER=%s --ve JUDGE_API_PROTOCOL=%s' \
    "$JUDGE_API_KEY" "$JUDGE_BASE_URL" "$JUDGE_MODEL" "$JUDGE_PROVIDER" "$JUDGE_API_PROTOCOL"
}

run_qwen() {
  [ -n "${QWEN_BASE:-}" ] && [ -n "${QWEN_KEY:-}" ] || { echo "[skip] qwen 端点缺失"; return; }
  OUT=$Q/g5-153-qwen
  mkdir -p "$OUT/trials"; rm -rf "${OUT:?}/trials"/* 2>/dev/null || true
  echo "=== start $(date '+%F %T') qwen ===" > "$OUT/qwen.log"
  # shellcheck disable=SC2046
  harbor trial start -p "$TASK_PATH" -a claude-code -m qwen3.8-max-0902 \
    --trial-name qwen38max-153 --trials-dir "$OUT/trials" \
    --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
    --ae ANTHROPIC_BASE_URL="$QWEN_BASE" \
    --ae ANTHROPIC_API_KEY="$QWEN_KEY" \
    --ae ANTHROPIC_AUTH_TOKEN="$QWEN_KEY" \
    $(common_ve) >> "$OUT/qwen.log" 2>&1
  echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/qwen.log"
}

run_gpt() {
  [ -n "${GPT_BASE:-}" ] && [ -n "${GPT_KEY:-}" ] || { echo "[skip] gpt 端点缺失"; return; }
  OUT=$Q/g5-153-gpt
  mkdir -p "$OUT/trials"; rm -rf "${OUT:?}/trials"/* 2>/dev/null || true
  echo "=== start $(date '+%F %T') gpt ===" > "$OUT/gpt.log"
  # shellcheck disable=SC2046
  harbor trial start -p "$TASK_PATH" -a claude-code -m gpt-5.6-sol \
    --trial-name gpt56sol-153 --trials-dir "$OUT/trials" \
    --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
    --ae ANTHROPIC_BASE_URL="$GPT_BASE" \
    --ae ANTHROPIC_API_KEY="$GPT_KEY" \
    --ae ANTHROPIC_AUTH_TOKEN="$GPT_KEY" \
    --ae ANTHROPIC_MODEL=gpt-5.6-sol \
    --ae ANTHROPIC_SMALL_FAST_MODEL=gpt-5.6-sol \
    --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=gpt-5.6-sol \
    --ae CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    $(common_ve) >> "$OUT/gpt.log" 2>&1
  echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/gpt.log"
}

run_opus() {
  [ -n "${OPUS_BASE:-}" ] && [ -n "${OPUS_KEY:-}" ] || { echo "[skip] opus 端点缺失"; return; }
  OUT=$Q/g5-153-opus
  mkdir -p "$OUT/trials"; rm -rf "${OUT:?}/trials"/* 2>/dev/null || true
  echo "=== start $(date '+%F %T') opus ===" > "$OUT/opus.log"
  # shellcheck disable=SC2046
  harbor trial start -p "$TASK_PATH" -a claude-code -m claude-opus-4-8 \
    --trial-name opus48-153 --trials-dir "$OUT/trials" \
    --agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode \
    --ae ANTHROPIC_BASE_URL="$OPUS_BASE" \
    --ae ANTHROPIC_API_KEY="$OPUS_KEY" \
    --ae ANTHROPIC_AUTH_TOKEN="$OPUS_KEY" \
    $(common_ve) >> "$OUT/opus.log" 2>&1
  echo "EXIT=$? done $(date '+%F %T')" >> "$OUT/opus.log"
}

case "${1:-all}" in
  qwen) run_qwen ;;
  gpt)  run_gpt ;;
  opus) run_opus ;;
  # 2026-10-12 甲方指示：opus 端点有问题，暂不跑；all 只跑 qwen + gpt。
  # 端点恢复后以 `g5_153_run.sh opus` 单独补跑即可。
  all)  run_qwen; run_gpt ;;
  *) echo "用法: g5_153_run.sh <qwen|gpt|opus|all>"; exit 2 ;;
esac
