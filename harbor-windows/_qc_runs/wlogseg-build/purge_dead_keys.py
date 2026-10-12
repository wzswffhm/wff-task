# -*- coding: utf-8 -*-
"""清理本地凭据副本文件里已失效的 api_key（只清空失效项，不动有效项）。

默认只报告；加 --fix 才写回。
"""
import hashlib
import json
import sys

SCRIPTS = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\skills\harbor-windows\scripts"
sys.path.insert(0, SCRIPTS)
import run_model_validation as R  # noqa: E402

P = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\skills\harbor-windows\scripts\model_endpoints.local.json"
FIX = "--fix" in sys.argv


def fp(k):
    return "sha256:%s len=%d" % (hashlib.sha256(k.encode()).hexdigest()[:10], len(k))


raw = json.load(open(P, encoding="utf-8"))
holder = raw if isinstance(raw, dict) else {"endpoints": raw}
eps = holder.get("endpoints") or holder.get("keys") or []

dead = []
alive = []
for e in eps:
    k = e.get("api_key") or ""
    label = e.get("key") or e.get("label") or e.get("name") or "?"
    if not k:
        print("  %-22s no key" % label)
        continue
    try:
        ok, status, text, _ = R.call_anthropic(
            e.get("base_url", ""), k, e.get("model", ""),
            "Reply with exactly: OK", e.get("auth", "x-api-key"), max_tokens=16)
    except Exception as ex:
        ok, status, text = False, None, "%s: %s" % (type(ex).__name__, ex)
    verdict = "ALIVE" if ok else "DEAD"
    print("  %-22s %s  %-6s status=%s %s" % (label, fp(k), verdict, status,
                                             str(text)[:80].replace("\n", " ")))
    if ok:
        alive.append(label)
    else:
        dead.append((e, label))

print("\n有效: %s" % (", ".join(alive) or "无"))
print("失效: %s" % (", ".join(l for _, l in dead) or "无"))

if FIX and dead:
    for e, _ in dead:
        e["api_key"] = ""
        if e.get("api_key_env") in (None, ""):
            e["api_key_env"] = ""
        e["status"] = "deprecated"
        e["note"] = "credential removed 2026-10-12 (endpoint rejected the key)"
    json.dump(raw, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("已清空 %d 个失效 api_key" % len(dead))
elif dead:
    print("（未改动；加 --fix 写回）")
