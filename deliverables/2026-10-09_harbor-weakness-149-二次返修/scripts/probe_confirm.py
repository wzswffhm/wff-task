# -*- coding: utf-8 -*-
"""确认三模型通道：打印完整回包的 model 字段，避免"型号被替换"假通道。"""
import json
import pathlib
import re
import urllib.error
import urllib.request


def load_env(p):
    out = {}
    p = pathlib.Path(p)
    if not p.is_file():
        return out
    for ln in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out

RUNNER = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner\.env.local")
judge = load_env(r"C:\Users\Administrator\.wff-creds\judge.env")
fanren_key = None
fp = pathlib.Path(r"C:\Users\Administrator\.wff-creds\fanrenapi.key")
if fp.is_file():
    m = re.search(r"sk-[A-Za-z0-9]+", fp.read_text(encoding="utf-8", errors="ignore"))
    if m:
        fanren_key = m.group(0)
fanren_key = fanren_key or "sk-kD3rBDui7Jj4Z1shaFzoMU5l8xjyrbOU99ij4uHrbvmN3UUE"
env = load_env(RUNNER)

CANDS = [
    ("opus48@4router", "https://4router.net", env.get("OPUS_API_KEY"), "claude-opus-4-8"),
    ("qwen38@aliyun/judge", judge.get("JUDGE_BASE_URL"), judge.get("JUDGE_API_KEY"), "qwen3.8-max-0902"),
    ("qwen38@aliyun/qwen", "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic", env.get("QWEN_API_KEY"), "qwen3.8-max-0902"),
    ("gpt56@fanrenapi", "https://fanrenapi.com", fanren_key, "gpt-5.6-sol"),
]


def probe(base, key, model, timeout=90):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 32,
                       "messages": [{"role": "user", "content": "Say OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key or "", "authorization": "Bearer " + (key or ""),
               "user-agent": "claude-cli/2.1.114 (external, cli)"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            return f"OK http={r.status} model={d.get('model')!r} stop={d.get('stop_reason')!r} usage={d.get('usage')}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:220].replace("\n", " ")
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__} {str(e)[:160]}"


print(f"runner .env.local OPUS_API_KEY present={bool(env.get('OPUS_API_KEY'))} len={len(env.get('OPUS_API_KEY') or '')}")
print(f"qwen key present={bool(env.get('QWEN_API_KEY'))}")
print("-" * 100)
for label, base, key, model in CANDS:
    if not base or not key:
        print(f"  {label:24s} -> SKIP (base={bool(base)} key={bool(key)})")
        continue
    print(f"  {label:24s} -> {probe(base, key, model)}")
