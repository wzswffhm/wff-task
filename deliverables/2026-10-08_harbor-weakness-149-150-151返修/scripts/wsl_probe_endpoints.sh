#!/usr/bin/env bash
# WSL 侧模型端点连通性验证（Anthropic Messages 协议）
# 用法: bash wsl_probe_endpoints.sh <ALIYUN_KEY> [BLVR_KEY] [JUDGE_KEY] [JUDGE_BASE]
set -u

ALIYUN_KEY="${1:-}"
BLVR_KEY="${2:-}"
JUDGE_KEY="${3:-}"
JUDGE_BASE="${4:-}"

ALIYUN="https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic"
BLVR="https://api.blvr.top"

probe() {
  local label="$1" base="$2" key="$3" model="$4"
  if [ -z "$key" ]; then
    printf '  %-34s -> SKIP (无 key)\n' "$label"
    return
  fi
  local body out code
  body=$(printf '{"model":"%s","max_tokens":32,"messages":[{"role":"user","content":"Reply with exactly: OK"}]}' "$model")
  out=$(curl -sS --max-time 60 -w '\n__CODE__%{http_code}' \
    -X POST "$base/v1/messages" \
    -H 'content-type: application/json' \
    -H 'anthropic-version: 2023-06-01' \
    -H "x-api-key: $key" \
    -d "$body" 2>&1)
  code=$(printf '%s' "$out" | sed -n 's/.*__CODE__//p')
  local payload
  payload=$(printf '%s' "$out" | sed 's/__CODE__[0-9]*$//' | tr -d '\n' | cut -c1-180)
  printf '  %-34s -> HTTP %s  %s\n' "$label" "${code:-ERR}" "$payload"
}

echo "=== WSL 侧端点连通性验证 $(date '+%F %T') ==="
echo "--- harbor-windows L3 端点（多模型区分度） ---"
probe "qwen3.8-max @ aliyun"  "$ALIYUN" "$ALIYUN_KEY" "qwen3.8-max"
probe "qwen3.8-max-0902 @ aliyun" "$ALIYUN" "$ALIYUN_KEY" "qwen3.8-max-0902"
probe "GLM-5.3 @ aliyun"       "$ALIYUN" "$ALIYUN_KEY" "GLM-5.3"
probe "Kimi K3 @ aliyun"       "$ALIYUN" "$ALIYUN_KEY" "Kimi K3"
probe "claude-opus-5 @ blvr"   "$BLVR"   "$BLVR_KEY"   "claude-opus-5"

echo "--- harbor-weakness 判官端点 ---"
if [ -n "$JUDGE_BASE" ]; then
  probe "judge qwen3.7-plus"   "$JUDGE_BASE" "$JUDGE_KEY" "qwen3.7-plus"
else
  echo "  judge 端点未提供（JUDGE_BASE_URL 缺失，需用户补充）"
fi
