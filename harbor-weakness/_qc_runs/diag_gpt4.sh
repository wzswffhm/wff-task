#!/bin/bash
# gpt4 判分故障诊断（verifier_error=1）
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2"

echo "=== trial 顶层 ==="
ls -la "$T" 2>&1 | head -14

echo
echo "=== agent 产物（artifacts/app/output） ==="
ls -la "$T/artifacts/app/output/" 2>&1 | head -14

echo
echo "=== reward.json ==="
cat "$T/verifier/reward.json" 2>/dev/null | head -c 400
echo
echo "=== reward_exit_message.json ==="
cat "$T/verifier/reward_exit_message.json" 2>/dev/null | head -c 600

echo
echo "=== verifier 目录 ==="
ls -la "$T/verifier/" 2>&1 | head -14
ls -la "$T/verifier/graded/" 2>&1 | head -14

echo
echo "=== exception.txt ==="
head -25 "$T/exception.txt" 2>/dev/null || echo "(无)"

echo
echo "=== agent 轨迹末尾（是否正常收尾） ==="
tail -c 700 "$T/agent/claude-code.txt" 2>/dev/null
