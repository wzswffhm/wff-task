#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 149 返修所需端点存活（judge / qwen / opus），键从既有 trial config 读取，绝不打印。"""
import glob
import json
import os
import re
import urllib.error
import urllib.request

BASE = "/home/wff/harbor-runs/FIN3-WKN-149"
WIN_JUDGE_ENV = "/mnt/c/Users/Administrator/.wff-creds/judge.env"


def load_cfg(pattern):
    fs = sorted(glob.glob(os.path.join(BASE, pattern, "*", "config.json")))
    if not fs:
        return None
    return json.load(open(fs[-1]))


def env_from(path):
    d = {}
    if not os.path.isfile(path):
        return d
    for ln in open(path, encoding="utf-8", errors="ignore"):
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            d[k.strip()] = v.strip().strip('"')
    return d


def probe(label, base, key, model, timeout=45):
    url = base.rstrip("/") + "/v1/messages"
    body = json.dumps({"model": model, "max_tokens": 16,
                       "messages": [{"role": "user", "content": "Reply with exactly: OK"}]}).encode()
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01",
               "x-api-key": key or "", "authorization": "Bearer " + (key or "")}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            m = re.search(r'"text"\s*:\s*"([^"]{0,40})', txt)
            return f"OK {r.status} {model} -> {(m.group(1) if m else txt[:60])!r}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {model} {e.read().decode('utf-8', 'replace')[:140]}"
    except Exception as e:  # noqa: BLE001
        return f"ERR {model} {type(e).__name__} {str(e)[:140]}"


jobs = []

cfgq = load_cfg("trials-qwen-f6")
if cfgq:
    e = cfgq["agent"]["env"]
    jobs.append(("qwen-agent", e["ANTHROPIC_BASE_URL"], e["ANTHROPIC_AUTH_TOKEN"], "qwen3.8-max-0902"))

cfo = load_cfg("trials-opus-f6")
if cfo:
    e = cfo["agent"]["env"]
    jobs.append(("opus-agent", e["ANTHROPIC_BASE_URL"], e["ANTHROPIC_AUTH_TOKEN"], "claude-opus-4-8"))

cfgj = load_cfg("trials-qwen-f6") or {}
jv = (cfgj.get("verifier") or {}).get("env") or {}
jenv = env_from(WIN_JUDGE_ENV)
jkey = jenv.get("JUDGE_API_KEY") or jv.get("JUDGE_API_KEY")
jbase = jenv.get("JUDGE_BASE_URL") or jv.get("JUDGE_BASE_URL")
jobs.append(("judge", jbase, jkey, jenv.get("JUDGE_MODEL", "qwen3.7-plus")))
jobs.append(("qwen-judgebase", jbase, jkey, "qwen3.8-max-0902"))

for label, b, k, m in jobs:
    if not b:
        print(f"{label}: SKIP no base")
        continue
    print(f"{label:16s} {probe(label, b, k, m)}")
