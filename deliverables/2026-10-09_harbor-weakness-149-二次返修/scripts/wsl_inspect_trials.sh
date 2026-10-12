#!/usr/bin/env bash
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8
for d in oracle qwen gpt opus; do
  echo "--- trials-$d ---"
  ls "$R/trials-$d/" 2>/dev/null
done
echo "=== 每个 trial 的 config.json（完整内容）==="
find "$R" -maxdepth 3 -name config.json | while read f; do
  echo "### $f"
  cat "$f"
  echo ""
done
echo "=== verifier environment_mode 检查（task/tests）==="
grep -r "environment_mode\|separate" /home/wff/harbor-tasks-fix8/FIN3-WKN-149/tests/*.sh 2>/dev/null | head
grep -r "environment_mode" /home/wff/harbor-tasks-fix8/FIN3-WKN-149/ 2>/dev/null | head
