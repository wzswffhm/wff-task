#!/usr/bin/env bash
# 三模型 regrade：复用 fix8 正式 trial 的 agent 产物，用 fix9 修复后的 rubrics 重跑 verifier
# 前置：oracle 已验证通过（G4=1.0）
set -euo pipefail
export PATH="$PATH:/home/wff/.local/bin"
export DOCKER_CONFIG=/home/wff/.docker-fix8

TASK_PATH="/home/wff/harbor-tasks-fix8/FIN3-WKN-149"
RUNROOT=/home/wff/harbor-runs/FIN3-WKN-149-fix9
VERIFIER_ENV_FILE=/mnt/c/Users/Administrator/.wff-creds/fin149_fix9_configs/verifier_env.json

# verifier env -> --ve 参数（python 展开）
mapfile -t VE_LINES < <(python3 -c "
import json
d=json.load(open('$VERIFIER_ENV_FILE'))
for k,v in d.items(): print(f'{k}={v}')
")
VE_ARGS=()
for l in "${VE_LINES[@]}"; do VE_ARGS+=(--ve "$l"); done
echo "verifier env: ${#VE_ARGS[@]} 参数"

declare -A SRC=(
  [qwen]="/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-qwen/FIN3-WKN-149__uqNx7ti"
  [gpt]="/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-gpt/FIN3-WKN-149__qsFcMtD"
  [opus]="/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/FIN3-WKN-149__vTPHQTW"
)

mkdir -p "$RUNROOT"

for m in qwen gpt opus; do
  src="${SRC[$m]}"
  outdir="$RUNROOT/regrade-$m"
  echo "=== [$m] regrade source=$src -> $outdir ==="
  if [ ! -d "$src" ]; then
    echo "  [SKIP] source 不存在: $src"
    continue
  fi
  if [ -d "$outdir" ]; then
    echo "  [SKIP] 已存在: $outdir (避免重复)"
    continue
  fi
  harbor trial regrade "$src" -p "$TASK_PATH" -o "$outdir" \
    "${VE_ARGS[@]}" \
    > "$RUNROOT/regrade_$m.out" 2>&1 &
  echo "  启动 pid=$!"
  sleep 2
done

echo ""
echo "=== 启动完成，日志 8 秒后 ==="
sleep 8
for m in qwen gpt opus; do
  echo "--- $m ---"
  tail -6 "$RUNROOT/regrade_$m.out" 2>/dev/null || echo "(尚无)"
done
