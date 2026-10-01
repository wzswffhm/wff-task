# -*- coding: utf-8 -*-
"""诊断 aliyun MaaS 上 qwen3.8-max-0902 的 thinking / max_tokens 行为。

背景：v2 的 qwen3.8-max-0902/run-1 在第 8 步 `stop_reason=max_tokens` 且正文为空，
与 GLM-5.3 曾出现的「thinking 吃光预算」现象同类。此处用一次最小请求判定：

  A. 不传 thinking 字段 + max_tokens=16000   —— 复现基线
  B. 不传 thinking 字段 + max_tokens=65536   —— 看是否只是预算不足
  C. thinking.type=disabled  + max_tokens=8192 —— 看端点是否支持关闭
  D. thinking.type=enabled   + budget=2048   —— 看 budget 是否被尊重

用法：
    python qwen_probe.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

ENDPOINTS = os.path.join(os.path.expanduser("~"), ".workbuddy",
                         "harbor-windows-endpoints.json")


def load_ep(key: str) -> dict:
    with open(ENDPOINTS, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for ep in cfg["endpoints"]:
        if ep["key"] == key:
            return ep
    raise SystemExit("endpoint not found: " + key)


def call(ep: dict, extra: dict | None, max_tokens: int, label: str) -> None:
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
    if ep.get("auth") == "authorization":
        headers["authorization"] = "Bearer " + ep["api_key"]
    else:
        headers["x-api-key"] = ep["api_key"]

    payload = {
        "model": ep["model"],
        "max_tokens": max_tokens,
        "stream": True,
        "messages": [{"role": "user", "content": "用一句话说明什么是幂等性。"}],
    }
    if extra:
        payload.update(extra)

    t0 = time.time()
    try:
        with httpx.stream("POST", url, headers=headers, json=payload,
                          timeout=httpx.Timeout(connect=30.0, read=300.0,
                                                write=120.0, pool=60.0)) as r:
            if r.status_code != 200:
                raw = r.read().decode("utf-8", "replace")
                print("[%s] HTTP %s @%.1fs  %s" % (label, r.status_code,
                                                  time.time() - t0, raw[:300]))
                return
            text_len = 0
            think_len = 0
            types: list[str] = []
            stop = None
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if not body or body == "[DONE]":
                    continue
                try:
                    ev = json.loads(body)
                except Exception:
                    continue
                t = ev.get("type")
                if t == "content_block_start":
                    types.append((ev.get("content_block") or {}).get("type"))
                elif t == "content_block_delta":
                    d = ev.get("delta") or {}
                    if d.get("type") == "text_delta":
                        text_len += len(d.get("text") or "")
                    elif d.get("type") == "thinking_delta":
                        think_len += len(d.get("thinking") or "")
                elif t == "message_delta":
                    stop = (ev.get("delta") or {}).get("stop_reason") or stop
    except Exception as e:
        print("[%s] EXC %s: %s" % (label, type(e).__name__, str(e)[:200]))
        return

    print("[%s] OK @%.1fs max_tokens=%d stop=%s blocks=%s text=%d think=%d"
          % (label, time.time() - t0, max_tokens, stop, types, text_len, think_len))


def main() -> None:
    ep = load_ep("qwen3.8-max")
    print("endpoint:", ep["base_url"], "model:", ep["model"])
    call(ep, None, 16000, "A no_thinking_field max16000")
    call(ep, None, 65536, "B no_thinking_field max65536")
    call(ep, {"thinking": {"type": "disabled"}}, 8192, "C thinking_disabled")
    call(ep, {"thinking": {"type": "enabled", "budget_tokens": 2048}}, 8192,
         "D thinking_enabled_budget2048")


if __name__ == "__main__":
    sys.exit(main())
