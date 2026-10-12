#!/usr/bin/env bash
echo "时间: $(date '+%F %T')"
echo "=== 149 rejudge 容器 ==="
docker ps --format '{{.Names}} {{.Status}}' | grep 'rejudge-FIN3-WKN-149' || echo '(无)'
echo "=== 149 rejudge reward 状态 ==="
RBASE=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-149/_rejudge
for m in qwen3.8-max-0902 gpt-5.6-sol claude-opus-4-8; do
  r="$RBASE/$m/verifier/reward.json"
  e="$RBASE/$m/verifier/reward_exit_message.json"
  printf '  %-20s ' "$m"
  if [ -f "$e" ]; then printf '[ERR] '; fi
  if [ -f "$r" ]; then tr -d '\n' < "$r"; else printf '(无)'; fi
  echo ''
done
echo "=== 149 rejudge 判分进度(容器内 test-stdout) ==="
for m in qwen3.8-max-0902 gpt-5.6-sol claude-opus-4-8; do
  printf '  %-20s ' "$m"
  docker exec "rejudge-FIN3-WKN-149-$m" sh -c 'tail -8 /logs/verifier/test-stdout.txt 2>/dev/null' 2>/dev/null \
    | grep -oE "'(R|N)[0-9]+'" | tail -1 || echo '(容器不在/无输出)'
  echo ''
done
echo "=== 149 rejudge 容器内当前判据 ==="
for m in qwen3.8-max-0902 gpt-5.6-sol claude-opus-4-8; do
  printf '  %-20s ' "$m"
  docker exec "rejudge-FIN3-WKN-149-$m" ps aux 2>/dev/null | grep -oE "\- '(R|N)[0-9]+'" | tail -1 || echo '?'
  echo ''
done
