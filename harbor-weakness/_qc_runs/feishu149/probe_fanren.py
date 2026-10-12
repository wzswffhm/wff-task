# -*- coding: utf-8 -*-
"""探测 fanrenapi 可用模型（重点 claude-opus-4-8 / gpt-5.6-sol）。"""
import json
import pathlib
import urllib.error
import urllib.request

key = None
for p in [pathlib.Path(r"C:\Users\Administrator\.wff-creds\fanrenapi.key")]:
    if p.is_file():
        import re
        m = re.search(r"sk-[A-Za-z0-9]+", p.read_text(encoding="utf-8", errors="ignore"))
        if m:
            key = m.group(0)
if not key:
    key = "sk-kD3rBDui7Jj4Z1shaFzoMU5l8xjyrbOU99ij4uHrbvmN3UUE"

BASE = "https://fanrenapi.com"


def probe(model, timeout=50):
    url = BASE.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 24,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key, "authorization": "Bearer " + key,
               "user-agent": "claude-cli/2.1.114 (external, cli)",
               "anthropic-beta": "fine-grained-tool-streaming-2025-05-14"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            return f"OK {r.status} " + txt[:200].replace("\n", " ")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__} {str(e)[:140]}"


def list_models():
    req = urllib.request.Request(BASE + "/v1/models", headers={"x-api-key": key,
                                                               "authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            txt = r.read().decode("utf-8", "replace")
            ids = json.loads(txt).get("data", [])
            return [d.get("id") for d in ids]
    except Exception as e:  # noqa: BLE001
        return [f"ERR {type(e).__name__} {str(e)[:120]}"]


ids = list_models()
print("models count:", len(ids))
hits = [i for i in ids if i and any(t in i.lower() for t in ("opus", "gpt-5", "sonnet", "qwen", "claude"))]
print("相关模型:", hits[:60])
for m in ["claude-opus-4-8", "claude-opus-4-5", "claude-opus-5", "gpt-5.6-sol", "claude-sonnet-4-6"]:
    print(f"  {m:22s} -> {probe(m)}")
