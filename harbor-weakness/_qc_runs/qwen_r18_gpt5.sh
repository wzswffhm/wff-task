#!/bin/bash
# qwen 唯一失分项 R18 详情 + gpt5 产出清单
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

echo "=== qwen 失分项 R18 详情 ==="
F=$(find "$R/g5-152v2-qwen2/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for c in d.get("reward", {}).get("criteria", []):
    if c["id"] == "R18":
        print("  id      :", c["id"])
        print("  value   :", c.get("value"), " raw:", c.get("raw"), " weight:", c.get("weight"))
        print("  desc    :", (c.get("description") or "")[:400])
        for k in ("reason", "reasoning", "explanation", "detail"):
            if c.get(k):
                print(f"  {k}:", str(c[k])[:500])
PY

echo
echo "=== gpt 第5轮 /app/output 清单 ==="
docker exec gpt56sol5-152v2__env-main-1 sh -c 'ls -la /app/output/ 2>/dev/null' 2>&1 | head -14

echo
echo "=== gpt 第5轮 工具调用统计 ==="
F2=$(find "$R/g5-152v2-gpt5/trials" -name claude-code.txt 2>/dev/null | head -1)
python3 - "$F2" <<'PY'
import json, sys, collections
tools = collections.Counter()
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    for c in ((d.get("message") or {}).get("content") or []):
        if isinstance(c, dict) and c.get("type") == "tool_use":
            tools[c.get("name")] += 1
print("  ", dict(tools))
PY
