#!/bin/bash
# 停 opus，确认 qwen/gpt 状态
systemctl stop g5-v3-opus.service 2>/dev/null
sleep 2
docker rm -f opus48-152v3__env-main-1 2>/dev/null || echo "opus container already gone"
echo "--- services ---"
for s in g5-v3-qwen g5-v3-gpt g5-v3-opus g4-152v3; do
  printf '%s=%s  ' "$s" "$(systemctl is-active $s.service)"
done
echo
echo "--- containers ---"
docker ps --format '  {{.Names}} | {{.Status}}'
