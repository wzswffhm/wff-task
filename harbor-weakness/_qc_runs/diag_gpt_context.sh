#!/bin/bash
# 诊断 gpt agent 上下文管理：是否触发过 auto-compact / harbor 支持哪些相关 kwargs
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2"

echo "=== 1. 轨迹里 compact / context 相关事件 ==="
grep -o '"subtype":"[a-z_]*"' "$T/agent/claude-code.txt" 2>/dev/null | sort | uniq -c | sort -rn | head -12
echo "--- 含 compact 的行数 ---"
grep -c 'compact' "$T/agent/claude-code.txt" 2>/dev/null
echo "--- 含 isCompactSummary / compact_boundary ---"
grep -o 'compact_boundary\|isCompactSummary\|auto-compact\|auto_compact' "$T/agent/claude-code.txt" 2>/dev/null | sort | uniq -c

echo
echo "=== 2. 各轮 input_tokens 走势（看是否被压缩过） ==="
python3 - "$T/agent/claude-code.txt" <<'PY'
import json, sys
rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    if d.get("type") == "assistant":
        u = (d.get("message") or {}).get("usage") or {}
        rows.append((u.get("input_tokens"), u.get("cache_read_input_tokens"), u.get("output_tokens")))
print(f"  assistant 轮次数 = {len(rows)}")
for i, (a, b, c) in enumerate(rows, 1):
    flag = "  <== 超窗" if (a or 0) > 200000 else ""
    print(f"   轮{i:>2}: input={a} cache_read={b} output={c}{flag}")
PY

echo
echo "=== 3. harbor claude_code agent 支持的 kwargs（找 context/compact/max_token） ==="
CL=$(python3 -c "import harbor.agents.installed.claude_code as m; print(m.__file__)" 2>/dev/null)
echo "  模块: $CL"
if [ -n "$CL" ]; then
  grep -nE 'context_window|compact|max_output_tokens|max_tokens|CLAUDE_CODE_[A-Z_]+' "$CL" 2>/dev/null | head -25
fi
