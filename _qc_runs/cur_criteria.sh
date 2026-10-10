#!/bin/bash
# 精确提取判官当前判据 ID（读 /proc/PID/cmdline 原始字节）
echo "=== $(date '+%F %T') ==="
for c in gpt56sol-152v4 opus48-152v4; do
  CID=$(docker ps -q --filter "name=$c" | head -1)
  [ -z "$CID" ] && { echo "[$c] 容器不在"; continue; }
  echo "[$c]"
  P=$(docker exec "$CID" bash -c 'pgrep -f "claude -p You are an evaluation judge" | head -1' 2>/dev/null | tr -d '\r\n')
  if [ -z "$P" ]; then
    echo "    判官: 无进程（间隙/完成）"
  else
    docker exec "$CID" bash -c "
      python3 - <<'PY' 2>/dev/null || python - <<'PY2' 2>/dev/null
import glob, re, os
pid = '$P'
try:
    raw = open(f'/proc/{pid}/cmdline','rb').read().decode('utf-8','replace')
except Exception as e:
    print('    读 cmdline 失败:', e); raise SystemExit
parts = [x for x in raw.split('\x00') if x]
txt = ' '.join(parts)
ids = re.findall(r\"'(R\d{2}|N0\d)'\", txt)
start = os.popen(f'ps -o lstart= -p {pid}').read().strip()
cpu = os.popen(f'ps -o cputimes= -p {pid}').read().strip()
model = ''
m = re.search(r'--model\s+(\S+)', txt)
if m: model = m.group(1)
print(f'    PID={pid} 启动={start} CPU={cpu}s')
print(f'    当前判据: {ids[0] if ids else \"(未在prompt中找到ID)\"}   model={model}')
PY
PY2" 2>&1 | sed 's/^/    /'
  fi
  # rewardkit 已判定的中间产物
  docker exec "$CID" bash -c 'ls -la /logs/verifier/graded/ 2>/dev/null | tail -6 | sed "s/^/    /"; echo "    --- 找 rewardkit 临时/进度文件 ---"; find /tmp /logs /app -maxdepth 4 -newermt "-20 minutes" -type f 2>/dev/null | grep -vE "sessions|\.jsonl|claude-code" | head -8 | sed "s/^/    /"' 2>&1
done

echo
echo "--- qwen 已完成的 details（对照它如何留痕）---"
QT=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-qwen/trials/qwen38max-152v4/verifier
ls -la "$QT/graded/" 2>/dev/null | sed 's/^/    /'
