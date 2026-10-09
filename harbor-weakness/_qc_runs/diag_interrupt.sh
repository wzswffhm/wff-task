#!/bin/bash
# 中断诊断
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

for d in g5-152v2-qwen g5-152v2-gpt3; do
  echo "########## $d ##########"
  echo "--- trials 目录 ---"
  ls -la "$R/$d/trials/" 2>&1 | head -8
  for t in "$R/$d/trials"/*/; do
    echo "--- trial: $t ---"
    ls -la "$t" 2>&1 | head -14
    echo "--- exception.txt ---"
    head -12 "$t/exception.txt" 2>/dev/null || echo "(无)"
    echo "--- agent/claude-code.txt 字节数 ---"
    wc -c "$t/agent/claude-code.txt" 2>/dev/null || echo "(无)"
    echo "--- trial.log 末尾 ---"
    tail -12 "$t/trial.log" 2>/dev/null || echo "(无)"
  done
done

echo
echo "=== keepers ==="
ps -eo pid,etime,args | grep 'sleep infinity' | grep -v grep || echo "(无 keeper!)"

echo
echo "=== systemd 单元状态 ==="
systemctl list-units --all --no-pager 2>&1 | grep -E 'g4-152v2|g5-' | head -12

echo
echo "=== 容器（含已退出） ==="
docker ps -a --format '{{.Names}} | {{.Status}}' | head -12

echo
echo "=== WSL 运行时长 / 是否重启过 ==="
stat -c '%y' /proc/1 2>/dev/null
cat /proc/uptime 2>/dev/null
