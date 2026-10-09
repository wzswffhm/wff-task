#!/bin/bash
# gpt4 判分被杀的详细证据
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2"

echo "=== verifier/graded/stderr.txt ==="
cat "$T/verifier/graded/stderr.txt" 2>/dev/null

echo
echo "=== verifier/test-stdout.txt ==="
cat "$T/verifier/test-stdout.txt" 2>/dev/null

echo
echo "=== trial.log 尾部 45 行 ==="
tail -45 "$T/trial.log" 2>/dev/null

echo
echo "=== agent 轨迹：最后 12 个工具名 ==="
grep -o '"name":"[A-Za-z]*"' "$T/agent/claude-code.txt" 2>/dev/null | tail -12

echo
echo "=== agent 轨迹里交付物文件名出现次数 ==="
grep -c 'FIN3-WKN-152_' "$T/agent/claude-code.txt" 2>/dev/null

echo
echo "=== 当前 harbor / trial 进程 ==="
ps -eo etimes,args --no-headers 2>/dev/null | grep -E 'harbor|trial start' | grep -v grep | head -6

echo
echo "=== gpt service 状态 ==="
systemctl is-active g5-gpt-152v2.service
systemctl status g5-gpt-152v2.service --no-pager 2>&1 | tail -8
