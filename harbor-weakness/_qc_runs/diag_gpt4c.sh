#!/bin/bash
# gpt4 取证：agent 最后 result 事件 + 判分是否真在进行 + qwen 阶段
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2"

echo "=== agent 最后一条 result 事件关键字段 ==="
tail -1 "$T/agent/claude-code.txt" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    for k in ('type','subtype','is_error','api_error_status','num_turns','terminal_reason','duration_ms','total_cost_usd'):
        print(f'  {k} = {d.get(k)}')
    r = str(d.get('result') or '')
    print('  result[:300] =', r[:300])
    u = d.get('usage') or {}
    print('  usage =', {k: u.get(k) for k in ('input_tokens','output_tokens')})
    mu = d.get('modelUsage') or {}
    for m, v in mu.items():
        print(f'  modelUsage[{m}] =', {k: v.get(k) for k in ('inputTokens','outputTokens','contextWindow')})
except Exception as e:
    print('  解析失败:', e)
"

echo
echo "=== 判分进程（test.sh） ==="
ps -eo etimes,args --no-headers 2>/dev/null | grep 'test.sh' | grep -v grep | head -2 | cut -c1-120

echo
echo "=== gpt 容器内判分状态 ==="
docker exec gpt56sol4-152v2__env-main-1 sh -c '
  echo -n "  /app/output 文件数: "; ls /app/output 2>/dev/null | wc -l
  echo -n "  /logs/verifier/graded 文件数: "; ls /logs/verifier/graded 2>/dev/null | wc -l
  echo "  graded 内容:"; ls -la /logs/verifier/graded 2>/dev/null | head -6
  echo "  当前判据进程:"; ps -eo etimes,args --no-headers 2>/dev/null | grep "claude -p" | grep -v grep | head -1 | cut -c1-140
' 2>&1

echo
echo "=== test-stdout.txt 行数（判分输出累积） ==="
wc -l "$T/verifier/test-stdout.txt" 2>/dev/null

echo
echo "=== qwen 容器阶段 ==="
docker exec qwen38max2-152v2__env-main-1 sh -c '
  echo -n "  /app/output 文件数: "; ls /app/output 2>/dev/null | wc -l
  echo -n "  agent 进程数: "; ps -eo args --no-headers 2>/dev/null | grep -c "claude --verbose"
  echo -n "  判分进程数: "; ps -eo args --no-headers 2>/dev/null | grep -c "claude -p"
' 2>&1
