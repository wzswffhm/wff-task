#!/usr/bin/env python
"""对比多个 Opus 端点：连通性 + 一个小的推理/代码能力探针。"""
import json
import time
import urllib.request

CANDS = [
    ("blvr", "https://api.blvr.top", "claude-opus-5",
     "sk-l8hraN17mCfgGZc2En6ecsHnQKYBRHMWZGMltWApY8KzRNoD"),
    ("ebondai", "https://api.ebondai.com", "claude-opus-5",
     "sk-e01ac61f23d90990a5672e5fa22806fc5890684d7f4acbd3209ca96d4b60a208"),
]

# 一个小探针：Windows 语义 + 边界条件，考察对"内容相同但 mtime 不同"的处理
PROBE = (
    "用 Python 写一个函数 should_copy(src_stat, dst_stat, src_hash, dst_hash) -> bool。"
    "规则：内容（hash）或修改时间（st_mtime_ns）或大小任一不同就必须返回 True；"
    "三者全同才返回 False。只输出函数代码，不要解释。"
)


def post(base, model, key, payload, timeout=120):
    req = urllib.request.Request(
        base.rstrip("/") + "/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8")), time.time() - t0


for name, base, model, key in CANDS:
    print("========== %s (%s) ==========" % (name, base))
    try:
        st, doc, dt = post(base, model, key, {
            "model": model, "max_tokens": 512,
            "messages": [{"role": "user", "content": PROBE}],
        })
        txt = "".join(b.get("text", "") for b in doc.get("content", []) if b.get("type") == "text")
        print("  http=%s %.1fs stop=%s usage_out=%s" % (
            st, dt, doc.get("stop_reason"), (doc.get("usage") or {}).get("output_tokens")))
        print("  model_returned=%s" % doc.get("model"))
        print("  --- reply ---")
        for ln in txt.splitlines():
            print("   |", ln)
    except Exception as e:
        print("  FAILED: %s %s" % (type(e).__name__, e))
        try:
            print("   body:", e.read().decode("utf-8")[:400])
        except Exception:
            pass
    print()
