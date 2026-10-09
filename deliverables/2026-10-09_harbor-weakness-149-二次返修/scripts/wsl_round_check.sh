#!/usr/bin/env bash
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8

echo "=== opus 重跑轮 vTPHQTW 的 result 事件 ==="
grep '"type":"result"' "$R/trials-opus/FIN3-WKN-149__vTPHQTW/agent/claude-code.txt" | tail -1 | cut -c1-700
echo
echo "=== opus 重跑轮 /app/output（agent 已收工） ==="
find "$R/trials-opus/FIN3-WKN-149__vTPHQTW/artifacts" -type f -printf '%10s %p\n' 2>/dev/null | sort -k2
echo
echo "=== 各执行体判分当前判据 ==="
for c in $(docker ps --format '{{.Names}}' | grep '149__' | sort); do
  echo "--- $c"
  docker exec "$c" ps aux 2>/dev/null | grep -o "- 'R[0-9]*'" | tail -2
  docker exec "$c" ps aux 2>/dev/null | grep -o "- 'N0[0-9]'" | tail -1
done
echo
echo "=== verifier 产物 ==="
for m in qwen gpt opus; do
  case $m in
    qwen) T=trials-qwen/FIN3-WKN-149__uqNx7ti;;
    gpt)  T=trials-gpt/FIN3-WKN-149__qsFcMtD;;
    opus) T=trials-opus/FIN3-WKN-149__vTPHQTW;;
  esac
  printf '  %-5s ' "$m"
  ls -l "$R/$T/verifier/" 2>/dev/null | tail -n +2 | awk '{printf "%s(%s) ", $9, $5}'
  echo
done
