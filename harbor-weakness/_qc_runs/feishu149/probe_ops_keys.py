# -*- coding: utf-8 -*-
"""探测可用的 opus / gpt 端点键（键只读不打印）。"""
import json
import pathlib
import re
import urllib.error
import urllib.request

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
ENV_SOURCES = [
    REPO / r"deliverables\2026-10-04_outside-harbor-win\runner\scripts_backup\env.local.pre_4router",
    REPO / r"deliverables\2026-10-04_outside-harbor-win\runner\scripts_backup\env.local.pre_ebond",
    REPO / r"deliverables\2026-10-06_win-rerun-epoch\scripts_backup\env.local.pre_lmuai",
    REPO / r"deliverables\2026-10-04_outside-harbor-win\runner\.env.local",
]
ALIYUN_FROM_PY = pathlib.Path(
    r"C:\Users\Administrator\.workbuddy\skills\harbor-windows\scripts\run_model_validation.py")

keys = {}
for src in ENV_SOURCES:
    if not src.is_file():
        print("missing env file:", src.name)
        continue
    for ln in src.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            keys.setdefault(k.strip(), v.strip().strip('"'))
    print("loaded", src.name, "keys:", sorted(k for k in keys if "KEY" in k or "TOKEN" in k))

if ALIYUN_FROM_PY.is_file():
    txt = ALIYUN_FROM_PY.read_text(encoding="utf-8", errors="ignore")
    for pat, name in [(r'"api_key":\s*"(sk-[^"]+)"', "ALIYUN_KEY_FROM_PY"),
                      (r'"api_key":\s*"(sk-l8[^"]+)"', "BLVR_KEY_FROM_PY")]:
        m = re.search(pat, txt)
        if m:
            keys.setdefault(name, m.group(1))

R4 = keys.get("OPUS_API_KEY")


def probe(label, base, key, model, timeout=40):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 16,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key or "", "authorization": "Bearer " + (key or "")}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return f"OK {r.status} {r.read().decode('utf-8','replace')[:70]!r}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.read().decode('utf-8','replace')[:120]}"
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__} {str(e)[:120]}"


TARGETS = [
    ("opus48@ebondai(OPUS)", "https://api.ebondai.com", keys.get("OPUS_API_KEY"), "claude-opus-4-8"),
    ("opus48@4router", "https://4router.net", keys.get("OPUS_API_KEY"), "claude-opus-4-8"),
    ("opus48@blvr", "https://api.blvr.top", keys.get("BLVR_KEY_FROM_PY"), "claude-opus-4-8"),
    ("opus5@ebondai", "https://api.ebondai.com", keys.get("OPUS_API_KEY"), "claude-opus-5"),
    ("gpt56@ebondai", "https://api.ebondai.com", keys.get("OPUS_API_KEY"), "gpt-5.6-sol"),
    ("gpt56@4router", "https://4router.net", keys.get("OPUS_API_KEY"), "gpt-5.6-sol"),
    ("opus48@lmuai", "https://api.lmuai.com", keys.get("OPUS_API_KEY"), "claude-opus-4-8"),
    ("glm53@lmuai", "https://api.lmuai.com", keys.get("GLM_API_KEY"), "glm-5.3"),
    ("opus48@aliyun(judgekey)", "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic",
     None, "claude-opus-4-8"),
]
# aliyun 用 judge.env 的键
import os
jpath = pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")
if jpath.is_file():
    for ln in jpath.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            keys.setdefault(k.strip(), v.strip().strip('"'))
TARGETS[-1] = ("opus48@aliyun(judgekey)", TARGETS[-1][1], keys.get("JUDGE_API_KEY"), "claude-opus-4-8")
TARGETS.append(("gpt56@aliyun(judgekey)", TARGETS[-1][1], keys.get("JUDGE_API_KEY"), "gpt-5.6-sol"))
TARGETS.append(("opus48@ark", "https://ark.cn-beijing.volces.com/api/coding", keys.get("KIMI_API_KEY"), "claude-opus-4-8"))

print("key names available:", sorted(k for k in keys if "KEY" in k))
print("-" * 90)
for label, base, key, model in TARGETS:
    if not key:
        print(f"  {label:26s} -> SKIP (no key)")
        continue
    print(f"  {label:26s} -> {probe(label, base, key, model)}")
