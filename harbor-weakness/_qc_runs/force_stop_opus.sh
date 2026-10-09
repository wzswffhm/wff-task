#!/bin/bash
# 彻底停 opus v3（上次 stop 因转义失败未生效）
systemctl stop g5-v3-opus.service 2>/dev/null && echo "stopped g5-v3-opus.service" || echo "stop returned nonzero"
sleep 3
echo -n "service state: "; systemctl is-active g5-v3-opus.service
docker rm -f opus48-152v3__env-main-1 2>/dev/null && echo "container removed" || echo "container already gone"
sleep 2
echo "--- 最终 services ---"
for s in g4-152v3 g5-v3-qwen g5-v3-gpt g5-v3-opus; do
  printf '  %-14s %s\n' "$s" "$(systemctl is-active $s.service 2>/dev/null)"
done
echo "--- 152v3 相关容器（应为空） ---"
docker ps --format '  {{.Names}} | {{.Status}}' | grep 152v3 || echo "  (无 152v3 容器)"
