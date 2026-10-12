# -*- coding: utf-8 -*-
"""opus_4router_probe.py —— 用 4router.net 端点给 218 题包做 Opus 5 探活。

只做两件事：
  1. 从 runner/.env.local 取 OPUS_* 端点参数（明文凭据不进仓库）
  2. 写出 run_model_validation.py 可用的端点配置 JSON 到 %TEMP%，并做一次
     流式 + tool_use 的短请求探活

用法：
    python opus_4router_probe.py [--runs 3]

输出：
    <TEMP>/wff-opus4router.endpoints.json   （单端点 opus-5，dir=opus-5）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = r"C:\Users\Administrator\Desktop\wff-task"
ENV_LOCAL = os.path.join(ROOT, "deliverables", "2026-10-04_outside-harbor-win",
                         "runner", ".env.local")
SKILL_SCRIPTS = os.path.join(ROOT, "harbor-windows", "skills", "harbor-windows", "scripts")
OUT_CFG = os.path.join(os.environ.get("TEMP", "/tmp"), "wff-opus4router.endpoints.json")


def parse_env_local(path: str) -> dict:
    vals = {}
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def build_endpoint(vals: dict) -> dict:
    key = vals["OPUS_API_KEY"]
    return {
        "key": "opus-5",
        "label": vals.get("OPUS_LABEL", "Opus 5"),
        "name": "claude-opus-5 @ 4router.net",
        "dir": vals.get("OPUS_DIR", "opus-5"),
        "model": vals.get("OPUS_MODEL", "claude-opus-5"),
        "provider": "4router.net 中转",
        "base_url": vals["OPUS_BASE_URL"],
        "api_key": key,
        "api_key_env": "",
        "auth": vals.get("OPUS_AUTH", "x-api-key"),
        "protocol": "anthropic",
        "max_tokens": int(vals.get("OPUS_MAX_TOKENS", "32000")),
        "request_timeout": float(vals.get("OPUS_REQUEST_TIMEOUT", "1800")),
        "stream": bool(int(vals.get("OPUS_STREAM", "1"))),
        "runs": 3,
        "role": "primary",
        "status": "active",
        "used_by": ["harbor-windows 218 模型验证（primary，3 轮）"],
        "note": "2026-10-12 由 runner/.env.local 还原；4router.net 必须流式（skill ref 08 §7.14）",
    }


def probe(ep: dict) -> int:
    sys.path.insert(0, SKILL_SCRIPTS)
    import agent_harness  # noqa: E402
    import httpx  # noqa: E402

    url = ep["base_url"].rstrip("/") + "/v1/messages"
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json",
               "x-api-key": ep["api_key"]}
    payload = {
        "model": ep["model"],
        "max_tokens": 256,
        "system": agent_harness.system_prompt(),
        "messages": [{"role": "user", "content": "先列出工作区文件，然后立刻调用 submit 结束。"}],
        "tools": agent_harness.TOOLS,
    }
    t0 = time.time()
    try:
        status, doc, raw = agent_harness._post(url, headers, payload, timeout=120)
    except Exception as e:  # noqa: BLE001
        print("  [FAIL] 传输异常: %s: %s" % (type(e).__name__, str(e)[:300]))
        return 1
    dt = time.time() - t0
    if status != 200 or doc is None:
        print("  [FAIL] HTTP %s (%.1fs) %s" % (status, dt, (raw or "")[:400]))
        return 1
    names = [b.get("name") for b in (doc.get("content") or []) if b.get("type") == "tool_use"]
    usage = doc.get("usage") or {}
    print("  [OK]   HTTP 200 (%.1fs) model=%s stop=%s tool_use=%s out_tokens=%s"
          % (dt, doc.get("model"), doc.get("stop_reason"), names,
             usage.get("output_tokens")))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-probe", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(ENV_LOCAL):
        print("未找到 %s" % ENV_LOCAL, file=sys.stderr)
        return 2
    vals = parse_env_local(ENV_LOCAL)
    for need in ("OPUS_BASE_URL", "OPUS_API_KEY", "OPUS_MODEL"):
        if not vals.get(need):
            print("env.local 缺少 %s" % need, file=sys.stderr)
            return 2

    ep = build_endpoint(vals)
    ep["runs"] = a.runs
    cfg = {"_comment": "由 opus_4router_probe.py 生成，含明文凭据，仅在 %TEMP% 存活",
           "endpoints": [ep]}
    with open(OUT_CFG, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)

    safe = dict(ep)
    safe["api_key"] = "<%d chars, %s…>" % (len(ep["api_key"]), ep["api_key"][:7])
    print("端点配置已写出: %s" % OUT_CFG)
    print(json.dumps(safe, ensure_ascii=False, indent=2))

    if a.no_probe:
        return 0
    print("探活（流式 + tool_use）...")
    return probe(ep)


if __name__ == "__main__":
    sys.exit(main())
