#!/usr/bin/env bash
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8
echo "=== gpt verifier 目录 ==="
ls -la "$R/trials-gpt/FIN3-WKN-149__qsFcMtD/verifier/" 2>&1
echo
echo "=== gpt trial.log 末尾 ==="
tail -6 "$R/trials-gpt/FIN3-WKN-149__qsFcMtD/trial.log" 2>&1
echo
echo "=== gpt.out ==="
tail -8 "$R/gpt.out" 2>&1
echo
echo "=== 容器 ==="
docker ps --format '{{.Names}}\t{{.Status}}'
echo
echo "=== 各 verifier 目录 ==="
for m in gpt qwen; do
  if [ "$m" = gpt ]; then T=trials-gpt/FIN3-WKN-149__qsFcMtD; else T=trials-qwen/FIN3-WKN-149__uqNx7ti; fi
  echo "--- $m ---"
  find "$R/$T/verifier" -type f -printf '%10s %p\n' 2>/dev/null || echo "(空)"
done
