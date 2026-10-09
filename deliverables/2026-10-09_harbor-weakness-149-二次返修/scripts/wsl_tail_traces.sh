#!/usr/bin/env bash
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8
echo "=== qwen 末尾 ==="
tail -2 "$R/trials-qwen/FIN3-WKN-149__uqNx7ti/agent/claude-code.txt" | cut -c1-500
echo
echo "=== gpt 末尾 ==="
tail -2 "$R/trials-gpt/FIN3-WKN-149__qsFcMtD/agent/claude-code.txt" | cut -c1-500
echo
echo "=== opus 重跑末尾 ==="
tail -2 "$R/trials-opus/FIN3-WKN-149__vTPHQTW/agent/claude-code.txt" | cut -c1-500
echo
echo "=== 各轨迹大小/mtime ==="
for f in "$R"/trials-qwen/FIN3-WKN-149__uqNx7ti/agent/claude-code.txt \
         "$R"/trials-gpt/FIN3-WKN-149__qsFcMtD/agent/claude-code.txt \
         "$R"/trials-opus/FIN3-WKN-149__vTPHQTW/agent/claude-code.txt; do
  [ -f "$f" ] && stat -c '%10s  %y  %n' "$f"
done
