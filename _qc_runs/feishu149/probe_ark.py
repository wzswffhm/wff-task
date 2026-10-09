# -*- coding: utf-8 -*-
"""深挖可用模型端点：ark / lmuai / aliyun，逐模型探测并打印回包片段。"""
import json
import pathlib
import re
import urllib.error
import urllib.request

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
ENV_SOURCES = [
    REPO / r"deliverables\2026-10-04_outside-harbor-win\runner\scripts_backup\env.local.pre_4router",
    REPO / r"deliverables\2026-10-06_win-rerun-epoch\scripts_backup\env.local.pre_lmuai",
]
keys = {}
for src in ENV_SOURCES:
    if not src.is_file():
        continue
    for ln in src.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            keys.setdefault(k.strip(), v.strip().strip('"'))
jpath = pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")
if jpath.is_file():
    for ln in jpath.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            keys.setdefault(k.strip(), v.strip().strip('"'))


def probe(base, key, model, timeout=50):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 24,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key or "", "authorization": "Bearer " + (key or "")}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return f"OK {r.status} " + r.read().decode("utf-8", "replace")[:220].replace("\n", " ")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__} {str(e)[:140]}"


ARK = "https://ark.cn-beijing.volces.com/api/coding"
LMUAI = "https://api.lmuai.com"
ALIYUN = "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic"

combos = [
    ("ark/kimi opus48", ARK, keys.get("KIMI_API_KEY"), "claude-opus-4-8"),
    ("ark/kimi gpt56", ARK, keys.get("KIMI_API_KEY"), "gpt-5.6-sol"),
    ("ark/kimi opus5", ARK, keys.get("KIMI_API_KEY"), "claude-opus-5"),
    ("ark/kimi kimi-k3", ARK, keys.get("KIMI_API_KEY"), "kimi-k3"),
    ("ark/kimi qwen3.8", ARK, keys.get("KIMI_API_KEY"), "qwen3.8-max-0902"),
    ("lmuai/glm gpt56", LMUAI, keys.get("GLM_API_KEY"), "gpt-5.6-sol"),
    ("lmuai/glm opus48", LMUAI, keys.get("GLM_API_KEY"), "claude-opus-4-8"),
    ("lmuai/glm glm-5.3", LMUAI, keys.get("GLM_API_KEY"), "glm-5.3"),
    ("aliyun/qwen opus48", ALIYUN, keys.get("QWEN_API_KEY"), "claude-opus-4-8"),
    ("aliyun/judge qwen3.8", ALIYUN, keys.get("JUDGE_API_KEY"), "qwen3.8-max-0902"),
    ("aliyun/qwen qwen3.8max", ALIYUN, keys.get("QWEN_API_KEY"), "qwen3.8-max-0902"),
]
print("keys:", sorted(k for k in keys if "KEY" in k))
for label, b, k, m in combos:
    if not k:
        print(f"  {label:24s} -> SKIP")
        continue
    print(f"  {label:24s} -> {probe(b, k, m)}")
