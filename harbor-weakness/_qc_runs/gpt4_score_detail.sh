#!/bin/bash
# 确认 gpt4 的最终得分口径：reward.json vs reward-details.json
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
T="$R/g5-152v2-gpt4/trials/gpt56sol4-152v2"

echo "=== reward.json（最终） ==="
cat "$T/verifier/reward.json" 2>/dev/null
echo
echo "=== reward.txt ==="
cat "$T/verifier/reward.txt" 2>/dev/null
echo
echo "=== reward_exit_message.json ==="
cat "$T/verifier/reward_exit_message.json" 2>/dev/null
echo
echo "=== graded 目录 ==="
ls -la "$T/verifier/graded/" 2>/dev/null

echo
echo "=== reward-details.json 里到底哪几条得分 ==="
F="$T/verifier/graded/reward-details.json"
[ -f "$F" ] || F="$T/verifier/reward-details.json"
python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d.get("reward", {})
crit = r.get("criteria", [])
print(f"  details.score = {r.get('score')}   条数 = {len(crit)}")
for c in crit:
    v = float(c.get("value") or 0)
    mark = "得" if v > 0 else "失"
    print(f"    [{mark}] {c['id']} value={v} raw={c.get('raw')} weight={c.get('weight')}")
PY

echo
echo "=== 对照：qwen 第2轮产出的 7 个文件 ==="
find "$R/g5-152v2-qwen2/trials" -path "*artifacts/app/output*" -type f 2>/dev/null | head -10
