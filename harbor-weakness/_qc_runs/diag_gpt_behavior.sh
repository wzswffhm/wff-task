#!/bin/bash
# 提取 gpt 的 Bash 命令与 subagent 用法，判断是否 fanrenapi 的工具调用适配问题
F=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v2-gpt4/trials/gpt56sol4-152v2/agent/claude-code.txt

python3 - "$F" <<'PY'
import json, sys, collections
cmds, tools, subs = [], collections.Counter(), []
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    msg = d.get("message") or {}
    for c in (msg.get("content") or []):
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use":
            name = c.get("name")
            tools[name] += 1
            inp = c.get("input") or {}
            if name == "Bash":
                cmds.append(str(inp.get("command"))[:160])
            if name == "Task":
                subs.append(str(inp.get("description") or inp.get("prompt"))[:100])

print("工具调用统计:", dict(tools))
print()
print("=== Bash 命令（前 18 条） ===")
for i, c in enumerate(cmds[:18], 1):
    print(f"  {i:>2}. {c}")
print()
print("=== 是否有写文件意图 ===")
w = [c for c in cmds if any(k in c for k in (">", "tee", "cat <<", "python3 -", "open("))]
print(f"  含写文件特征的 Bash 命令数 = {len(w)}")
for c in w[:8]:
    print("   *", c[:150])
print()
print("=== subagent 任务描述（前 8 条） ===")
for i, s in enumerate(subs[:8], 1):
    print(f"  {i}. {s}")
PY

echo
echo "=== 轨迹里 tool_result 是否成对出现（适配是否正常） ==="
echo -n "  tool_use 数: "; grep -o '"type":"tool_use"' "$F" | wc -l
echo -n "  tool_result 数: "; grep -o '"type":"tool_result"' "$F" | wc -l
echo -n "  含 is_error 的 tool_result 数: "; grep -o '"type":"tool_result","content":[^}]*"is_error":true' "$F" | wc -l
