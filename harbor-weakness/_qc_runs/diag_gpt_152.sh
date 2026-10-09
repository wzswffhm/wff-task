#!/bin/bash
# gpt-5.6-sol 0 分诊断：判定"真弱分"还是"故障分"
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt/trials/gpt56sol-152v2"

echo "=== trial 顶层 ==="
ls -la "$T" 2>&1 | head -14

echo
echo "=== artifacts 产物 ==="
ls -la "$T/artifacts/app/output/" 2>&1 | head -14

echo
echo "=== artifacts/manifest.json ==="
head -c 900 "$T/artifacts/manifest.json" 2>/dev/null
echo

echo
echo "=== agent 目录 ==="
ls -la "$T/agent/" 2>&1 | head -12

echo
echo "=== claude-code.txt 末尾（找最后一条 result 事件） ==="
tail -c 2200 "$T/agent/claude-code.txt" 2>/dev/null
echo

echo
echo "=== result.json 摘要 ==="
python3 - <<'PY' 2>/dev/null || echo "(python3 解析失败)"
import json, pathlib
p = pathlib.Path("/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v2-gpt/trials/gpt56sol-152v2/result.json")
d = json.loads(p.read_text(encoding="utf-8"))
def dig(o, keys, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in keys:
                print(f"{pre}{k} = {str(v)[:200]}")
            dig(v, keys, pre + "  ")
    elif isinstance(o, list):
        for it in o[:3]:
            dig(it, keys, pre + "  ")
dig(d, {"terminal_reason", "is_error", "stop_reason", "num_turns", "duration_ms",
        "error", "exception", "reward", "criteria_counted", "verifier_error", "subtype"})
PY
