#!/bin/bash
# 对比 gpt / qwen 的上下文管理信号，判断失败是否可修
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
G="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2/agent/claude-code.txt"
Q=$(find "$R/g5-152v2-qwen2/trials" -name claude-code.txt 2>/dev/null | head -1)

for pair in "gpt:$G" "qwen:$Q"; do
  label="${pair%%:*}"; f="${pair#*:}"
  echo "########## $label ##########"
  echo "  文件: $f"
  [ -f "$f" ] || { echo "  (不存在)"; continue; }
  echo -n "  compact 相关出现次数: "; grep -c -i 'compact' "$f" 2>/dev/null
  echo "  compact 命中行（前 2 条，截断 200 字符）:"
  grep -i -m2 'compact' "$f" 2>/dev/null | cut -c1-200 | sed 's/^/    /'
  echo -n "  'Context low' / 'context left' 提示: "; grep -c -i 'context low\|context left\|context limit' "$f" 2>/dev/null
  echo -n "  Task(subagent) 启动数: "; grep -o '"subtype":"task_started"' "$f" 2>/dev/null | wc -l
  echo -n "  Write 工具调用数: "; grep -o '"name":"Write"' "$f" 2>/dev/null | wc -l
  echo -n "  Bash 工具调用数: "; grep -o '"name":"Bash"' "$f" 2>/dev/null | wc -l
  echo
done

echo "=== 容器内是否残留 gpt 的产物线索 ==="
echo -n "  gpt /app/output: "; docker exec gpt56sol4-152v2__env-main-1 sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null
docker exec gpt56sol4-152v2__env-main-1 sh -c 'ls -la /app/output/ 2>/dev/null | head -4' 2>/dev/null
echo -n "  gpt 是否创建过临时脚本: "
docker exec gpt56sol4-152v2__env-main-1 sh -c 'ls /app/*.py /app/*.csv /app/*.xlsx 2>/dev/null | head -5' 2>/dev/null || echo "(无)"
docker exec gpt56sol4-152v2__env-main-1 sh -c 'ls -la /app/ | head -8' 2>/dev/null
