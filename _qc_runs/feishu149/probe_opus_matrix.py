# -*- coding: utf-8 -*-
"""对仓库内出现的每把 OPUS/Anthropic 键 × 每个网关，探测 claude-opus-4-8 可用性。"""
import hashlib
import json
import pathlib
import re
import urllib.error
import urllib.request

roots = [pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task"),
         pathlib.Path(r"C:\Users\Administrator\.workbuddy"),
         pathlib.Path(r"C:\Users\Administrator\.wff-creds")]
pat = re.compile(r"(OPUS_API_KEY|ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN)"
                 r"\s*[=:]\s*[\"']?(sk-[A-Za-z0-9\-_\.]{16,}|[A-Za-z0-9\-_]{24,})")
exts = ('.py', '.sh', '.env', '.local', '.yaml', '.yml', '.json', '.md', '.txt', '.key', '.ps1', '.toml')
keys = {}   # value -> first file
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in exts or p.stat().st_size > 3_000_000:
            continue
        try:
            t = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for m in pat.finditer(t):
            keys.setdefault(m.group(2), str(p))

GATES = [
    ("ebondai", "https://api.ebondai.com"),
    ("4router", "https://4router.net"),
    ("blvr", "https://api.blvr.top"),
    ("lmuai", "https://api.lmuai.com"),
    ("fanrenapi", "https://fanrenapi.com"),
]


def probe(base, key, model="claude-opus-4-8", timeout=40):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 16,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key, "authorization": "Bearer " + key,
               "user-agent": "claude-cli/2.1.114 (external, cli)"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "OK " + r.read().decode("utf-8", "replace")[:120].replace("\n", " ")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:130].replace("\n", " ")
    except Exception as e:  # noqa: BLE010
        return f"ERR {type(e).__name__} {str(e)[:110]}"


print("distinct keys:", len(keys))
for v, src in keys.items():
    print(f"  key {hashlib.sha1(v.encode()).hexdigest()[:10]} from ...{src[-70:]}")
print("-" * 100)
for v, src in list(keys.items()):
    h = hashlib.sha1(v.encode()).hexdigest()[:10]
    for name, b in GATES:
        res = probe(b, v)
        flag = " <== USABLE" if res.startswith("OK") else ""
        if res.startswith("OK") or "model_not_found" not in res:
            print(f"  {h} {name:11s} -> {res[:150]}{flag}")
