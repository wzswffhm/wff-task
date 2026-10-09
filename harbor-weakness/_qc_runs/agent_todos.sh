#!/bin/bash
# agent 阶段进度：从 claude-code 轨迹里解析 TodoWrite 清单
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
parse_todos() {  # $1 = claude-code.txt 路径, $2 = label
  f="$1"; label="$2"
  [ -f "$f" ] || { echo "  $label: (无轨迹)"; return; }
  python3 - "$f" "$label" <<'PY'
import json, sys
f, label = sys.argv[1], sys.argv[2]
todos = []
tool_calls = 0
for line in open(f, encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    for c in ((d.get("message") or {}).get("content") or []):
        if isinstance(c, dict) and c.get("type") == "tool_use":
            tool_calls += 1
            if c.get("name") == "TodoWrite":
                todos = (c.get("input") or {}).get("todos") or []
    # 最新 TodoWrite 的 status 可能在 tool_result 里，但简单起见取最后一份 input
if todos:
    done = sum(1 for t in todos if t.get("status") == "completed")
    inprog = sum(1 for t in todos if t.get("status") == "in_progress")
    pend = sum(1 for t in todos if t.get("status") == "pending")
    cur = ""
    for t in todos:
        if t.get("status") == "in_progress":
            cur = (t.get("activeForm") or t.get("content") or "")[:38]
    print(f"  {label}: todo {done}/{len(todos)} 完成, {inprog} 进行中, {pend} 待办 | 当前: {cur}")
else:
    print(f"  {label}: 尚无 TodoWrite（已 {tool_calls} 次工具调用）")
PY
}

# qwen
QC=$(find "$Q"/g5-152v3-qwen/trials -name claude-code.txt 2>/dev/null | head -1)
parse_todos "$QC" "qwen"
# gpt
GC=$(find "$Q"/g5-152v3-gpt/trials -name claude-code.txt 2>/dev/null | head -1)
parse_todos "$GC" "gpt "
