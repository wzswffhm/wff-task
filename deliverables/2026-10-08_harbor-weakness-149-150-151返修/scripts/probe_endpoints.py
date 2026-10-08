"""Probe the model/judge endpoints recorded in this project for liveness.

Keys are read from on-disk env files and NEVER printed.
"""
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
]
ALIYUN_FROM_PY = pathlib.Path(
    r"C:\Users\Administrator\.workbuddy\skills\harbor-windows\scripts\run_model_validation.py")

keys = {}
per_source = {}
for src in ENV_SOURCES:
    if not src.is_file():
        continue
    d = {}
    for ln in src.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            d[k.strip()] = v.strip().strip('"')
    per_source[src.name.replace("env.local.", "")] = d
    for k, v in d.items():
        keys.setdefault(k, v)

R4 = per_source.get("pre_ebond", {}).get("OPUS_API_KEY")   # 4router key
KIMI = keys.get("KIMI_API_KEY")

if ALIYUN_FROM_PY.is_file():
    txt = ALIYUN_FROM_PY.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'"api_key":\s*"(sk-[^"]+)"', txt)
    if m:
        keys.setdefault("ALIYUN_KEY_FROM_PY", m.group(1))
    m2 = re.search(r'"api_key":\s*"(sk-l8[^"]+)"', txt)
    if m2:
        keys.setdefault("BLVR_KEY_FROM_PY", m2.group(1))

ALIYUN = "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic"

# (label, base_url, key, model, auth)
TARGETS = [
    ("judge qwen3.7-plus @ aliyun",   ALIYUN,                              keys.get("QWEN_API_KEY"),  "qwen3.7-plus",      "x-api-key"),
    ("qwen3.8-max-0902 @ aliyun",     ALIYUN,                              keys.get("QWEN_API_KEY"),  "qwen3.8-max-0902",  "x-api-key"),
    ("qwen3.8-max @ aliyun",          ALIYUN,                              keys.get("QWEN_API_KEY"),  "qwen3.8-max",       "x-api-key"),
    ("opus-5 @ ebondai",              "https://api.ebondai.com",           keys.get("OPUS_API_KEY"),  "claude-opus-5",     "x-api-key"),
    ("opus-4-8 @ ebondai",            "https://api.ebondai.com",           keys.get("OPUS_API_KEY"),  "claude-opus-4-8",   "x-api-key"),
    ("gpt-5.6-sol @ ebondai",         "https://api.ebondai.com",           keys.get("OPUS_API_KEY"),  "gpt-5.6-sol",       "x-api-key"),
    ("opus-4-8 @ blvr",               "https://api.blvr.top",              keys.get("BLVR_KEY_FROM_PY"), "claude-opus-4-8", "x-api-key"),
    ("glm-5.3 @ lmuai",               "https://api.lmuai.com",             keys.get("GLM_API_KEY"),   "glm-5.3",           "x-api-key"),
    ("opus-5 @ 4router",              "https://4router.net",               R4,                        "claude-opus-5",     "x-api-key"),
    ("opus-4-8 @ 4router",            "https://4router.net",               R4,                        "claude-opus-4-8",   "x-api-key"),
    ("gpt-5.6-sol @ 4router",         "https://4router.net",               R4,                        "gpt-5.6-sol",       "x-api-key"),
    ("ark coding + kimi-k3",          "https://ark.cn-beijing.volces.com/api/coding", KIMI,           "kimi-k3",           "authorization"),
    ("ark coding + gpt-5.6-sol",      "https://ark.cn-beijing.volces.com/api/coding", KIMI,           "gpt-5.6-sol",       "authorization"),
    ("qwen3.7-plus @ aliyun (2nd key)", ALIYUN,                            keys.get("ALIYUN_KEY_FROM_PY"), "qwen3.7-plus", "x-api-key"),
]


def probe(base, key, model, auth):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 16,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if auth == "authorization":
        headers["authorization"] = "Bearer " + (key or "")
    else:
        headers["x-api-key"] = key or ""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            txt = r.read().decode("utf-8", "replace")
            return r.status, txt[:160]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:160]
    except Exception as e:  # noqa: BLE001
        return "ERR", str(e)[:160]


print("keys found:", {k: ("set" if v else "MISSING") for k, v in keys.items()})
print("-" * 100)
for label, base, key, model, auth in TARGETS:
    if not key:
        print(f"  {label:28s} -> SKIP (no key)")
        continue
    status, snippet = probe(base, key, model, auth)
    snippet = snippet.replace("\n", " ")
    print(f"  {label:28s} -> {status}  {snippet}")
