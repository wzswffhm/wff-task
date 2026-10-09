#!/usr/bin/env bash
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8
docker rm -f fin3-wkn-149__6ab4ng8__env-main-1 >/dev/null 2>&1

echo "=== 容器 ==="
docker ps --format '{{.Names}}\t{{.Status}}'

for m in qwen gpt; do
  if [ "$m" = qwen ]; then
    T=trials-qwen/FIN3-WKN-149__uqNx7ti; C=fin3-wkn-149__uqnx7ti__env-main-1
  else
    T=trials-gpt/FIN3-WKN-149__qsFcMtD; C=fin3-wkn-149__qsfcmtd__env-main-1
  fi
  echo
  echo "=== $m 轮数 ==="
  grep -c '"type":"assistant"' "$R/$T/agent/claude-code.txt" 2>/dev/null || echo 0
  echo "--- $m /app/output ---"
  docker exec "$C" find /app/output -type f -printf '%10s %f\n' 2>/dev/null | sort -k2
done

echo
echo "=== opus 重判 verifier 目录 ==="
ls -l "$R/rejudge-opus/logs/verifier/" 2>/dev/null
echo "--- opus 重判 reward ---"
cat "$R/rejudge-opus/logs/verifier/reward.json" 2>/dev/null

echo
echo "=== opus 重跑（vTPHQTW）轮数 ==="
grep -c '"type":"assistant"' "$R/trials-opus/FIN3-WKN-149__vTPHQTW/agent/claude-code.txt" 2>/dev/null || echo 0
docker exec fin3-wkn-149__vtphqtw__env-main-1 find /app/output -type f -printf '%10s %f\n' 2>/dev/null | sort -k2
