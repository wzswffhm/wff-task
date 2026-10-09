#!/bin/bash
# 1) 正确定位 claude-code 包并 grep 窗口/压缩相关开关  2) 看 gpt 最后几轮的 input 规模
C=gpt56sol4-152v2__env-main-1
F=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v2-gpt4/trials/gpt56sol4-152v2/agent/claude-code.txt

echo "=== claude-code 包目录 ==="
docker exec "$C" sh -c 'ls /usr/local/lib/node_modules/ 2>/dev/null; echo "---"; ls /usr/local/lib/node_modules/@anthropic-ai/claude-code/ 2>/dev/null | head -12' 2>&1

echo
echo "=== 在包目录里 grep 关键开关 ==="
docker exec "$C" sh -c 'D=/usr/local/lib/node_modules/@anthropic-ai/claude-code; grep -rhoE "CLAUDE_CODE_[A-Z0-9_]+" $D 2>/dev/null | sort -u | head -40' 2>&1

echo
echo "=== 上下文/压缩标识统计 ==="
docker exec "$C" sh -c 'D=/usr/local/lib/node_modules/@anthropic-ai/claude-code; grep -rhoE "(autoCompact|auto_compact|compactThreshold|contextWindow|context_window|MAX_OUTPUT_TOKENS|maxOutputTokens)" $D 2>/dev/null | sort | uniq -c | sort -rn | head -15' 2>&1

echo
echo "=== gpt 最后 12 轮 assistant usage（主循环规模） ==="
python3 - "$F" <<'PY'
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
        m = d.get("message") or {}
        if m.get("model") == "<synthetic>":
            continue
        u = m.get("usage") or {}
        rows.append((m.get("model"), u.get("input_tokens"), u.get("cache_read_input_tokens"), u.get("output_tokens")))
for r in rows[-12:]:
    print(f"  model={r[0]} input={r[1]} cache_read={r[2]} output={r[3]}")
print(f"  总 assistant（非 synthetic）= {len(rows)}")
big = [r for r in rows if (r[1] or 0) > 150000]
print(f"  input>150K 的轮次 = {len(big)}")
PY
