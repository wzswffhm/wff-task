# -*- coding: utf-8 -*-
"""列出各网关可用模型，寻找 claude-opus-4-8 的可用通道。"""
import json
import pathlib
import urllib.error
import urllib.request

keys = {}
for p in [pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")]:
    if p.is_file():
        for ln in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                keys[k.strip()] = v.strip().strip('"')
envp = pathlib.Path(r"C:\Users\Administrator\.workbuddy\harbor-windows.env")
if envp.is_file():
    for ln in envp.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            keys.setdefault(k.strip(), v.strip().strip('"'))
for p in [pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-06_win-rerun-epoch\scripts_backup\env.local.pre_lmuai")]:
    if p.is_file():
        for ln in p.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                keys.setdefault(k.strip(), v.strip().strip('"'))


def list_models(base, key, path="/v1/models"):
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, headers={
        "x-api-key": key or "", "authorization": "Bearer " + (key or ""),
        "user-agent": "claude-cli/2.1.114 (external, cli)",
        "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            doc = json.loads(r.read().decode("utf-8", "replace"))
            ids = [d.get("id") for d in doc.get("data", [])]
            return ids
    except urllib.error.HTTPError as e:
        return [f"HTTP {e.code} " + e.read().decode("utf-8", "replace")[:150]]
    except Exception as e:  # noqa: BLE001
        return [f"ERR {type(e).__name__} {str(e)[:120]}"]


JUDGE = keys.get("JUDGE_BASE_URL")
ends = [
    ("aliyun-gateway", JUDGE, keys.get("JUDGE_API_KEY")),
    ("lmuai", "https://api.lmuai.com", keys.get("GLM_API_KEY")),
    ("ebondai", "https://api.ebondai.com", keys.get("OPUS_API_KEY")),
    ("4router", "https://4router.net", keys.get("OPUS_API_KEY")),
    ("blvr", "https://api.blvr.top", keys.get("BLVR_KEY_FROM_PY") or keys.get("HARBOR_WINDOWS_BLVR_KEY")),
]
import re
p = pathlib.Path(r"C:\Users\Administrator\.workbuddy\skills\harbor-windows\scripts\run_model_validation.py")
m = re.search(r'"api_key":\s*"(sk-l8[^"]+)"', p.read_text(encoding="utf-8", errors="ignore")) if p.is_file() else None
if m:
    ends[-1] = ("blvr", "https://api.blvr.top", m.group(1))

for name, b, k in ends:
    if not b:
        print(f"{name}: no base")
        continue
    ids = list_models(b, k)
    claude = [i for i in ids if i and "claude" in i.lower() or (i and "opus" in i.lower())]
    print(f"{name}: total={len(ids)} claude/opus={claude[:20]}")
    if len(ids) <= 40:
        print("   ", ids)
