# -*- coding: utf-8 -*-
"""检查 models.local.json 的端点顺序、dir 冲突与 --only 的选择结果。"""
import hashlib
import json

P = r"C:\Users\Administrator\Desktop\wff-task\models.local.json"
cfg = json.load(open(P, encoding="utf-8"))
eps = cfg["endpoints"] if isinstance(cfg, dict) else cfg

print("total endpoints: %d" % len(eps))
print("%-3s %-16s %-11s %-26s %-28s %-8s %s"
      % ("#", "key", "dir", "status", "base_url", "model", "key fp"))
for i, e in enumerate(eps, 1):
    k = e.get("api_key") or ""
    fp = "-" if not k else hashlib.sha256(k.encode()).hexdigest()[:8]
    env = e.get("api_key_env") or ""
    print("%-3d %-16s %-11s %-26s %-28s %-8s %s%s"
          % (i, e.get("key", ""), e.get("dir", ""), e.get("status", "")[:26],
             e.get("base_url", "")[:28], str(e.get("model", ""))[:8], fp,
             (" env=" + env) if env else ""))

print()
dupes = {}
for e in eps:
    dupes.setdefault(e.get("dir"), []).append(e.get("key"))
print("dir collisions:")
for d, ks in dupes.items():
    if len(ks) > 1:
        print("  dir=%-11s <- %s" % (d, ks))

print()
print("key collisions:")
kc = {}
for e in eps:
    kc.setdefault(e.get("key"), []).append(e.get("dir"))
for k, ds in kc.items():
    if len(ds) > 1:
        print("  key=%-16s <- dirs %s" % (k, ds))

print()
for want in ("opus-5", "glm-5.3", "qwen3.8-max", "kimi-k3"):
    hit = [e for e in eps if e.get("key") == want or e.get("dir") == want]
    print("--only %-12s -> %d match(es):" % (want, len(hit)))
    for e in hit:
        print("      key=%-16s base_url=%-30s status=%s" % (
            e.get("key"), e.get("base_url"), e.get("status")))
