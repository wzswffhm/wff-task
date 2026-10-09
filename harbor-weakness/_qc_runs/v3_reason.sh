#!/bin/bash
# 判官对 R30/R31/R32/R33 的判词（为何给 yes）
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
F=$(find "$R/g5-152v3-qwen/trials" -maxdepth 4 -name reward-details.json 2>/dev/null | head -1)
echo "=== qwen R30-R33 判词 ==="
python3 - "$F" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for c in d.get("reward", {}).get("criteria", []):
    if c["id"] in ("R30","R31","R32","R33"):
        print(f"\n--- {c['id']} value={c.get('value')} raw={c.get('raw')} ---")
        for k in ("reasoning","reason","explanation","justification","feedback","detail","evidence"):
            if c.get(k):
                print(f"  [{k}]", str(c[k])[:600])
        # 打印除描述外所有键，找判词字段
        extra = {k: v for k, v in c.items() if k not in ("id","name","description","type","weight","value","raw") and v}
        if extra:
            print("  [其他字段]", json.dumps(extra, ensure_ascii=False)[:700])
PY
