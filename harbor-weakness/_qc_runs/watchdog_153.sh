#!/bin/bash
# 看守：等待 G4 判分结束（oracle.log 出现完成标记且 verifier_error=0），
# 随后自动启动 G5 的 qwen3.8-max-0902 执行体（与 judge 共用同一 key，必须串行）。
set -u
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
LOG=$Q/g4-153/oracle.log
WAITLOG=$Q/g4-153/watchdog.log

echo "=== watchdog start $(date '+%F %T') ===" > "$WAITLOG"
for i in $(seq 1 240); do
  if grep -q '^EXIT=' "$LOG" 2>/dev/null; then
    break
  fi
  sleep 30
done

if ! grep -q '^EXIT=' "$LOG" 2>/dev/null; then
  echo "[!!] 等待 G4 超时（2 小时）" >> "$WAITLOG"
  exit 1
fi

RC=$(grep '^EXIT=' "$LOG" | tail -1)
VE=$(python3 - <<'PY' 2>/dev/null || echo "nan"
import json,glob
p=glob.glob('/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4-153/trials/oracle-153/verifier/reward.json')
print(json.load(open(p[0]))['verifier_error'] if p else 'nan')
PY
)
echo "G4 $RC verifier_error=$VE  $(date '+%F %T')" >> "$WAITLOG"

if [ "$VE" != "0.0" ] && [ "$VE" != "0" ]; then
  echo "[!!] G4 未取得有效判分（verifier_error=$VE），不启动 G5" >> "$WAITLOG"
  exit 2
fi

echo "=== 启动 G5 qwen $(date '+%F %T') ===" >> "$WAITLOG"
cd "$Q" || exit 90
setsid nohup bash g5_153_run.sh qwen >> "$WAITLOG" 2>&1 < /dev/null &
echo "started pid=$!" >> "$WAITLOG"
