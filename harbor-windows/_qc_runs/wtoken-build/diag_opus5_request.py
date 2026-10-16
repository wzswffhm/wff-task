"""Isolate why claude-opus-5 returns empty for the agent but not for a bare POST.

The agent sends model/max_tokens/system/messages/tools. A bare POST with only
model/max_tokens/messages succeeds. This script replays the request with each
extra field added one at a time, using urllib exactly as the agent does, so the
difference is measured rather than guessed.

Run: python diag_opus5_request.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
BUILD = ROOT / "harbor-windows" / "_qc_runs" / "wtoken-build"
PKG = ROOT / "harbor-windows" / "wfflab__wtoken-221-v1.0.0-delivery"

sys.path.insert(0, str(BUILD / "harbor_agent"))


def load_endpoint() -> dict:
    cfg = json.loads((ROOT / "models.local.json").read_text(encoding="utf-8"))
    for item in cfg["endpoints"]:
        if item.get("key") == "opus-5":
            return item
    raise SystemExit("opus-5 endpoint not found")


def post(url: str, key: str, payload: dict, timeout: int = 120) -> tuple[int, dict | str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("x-api-key", key)
    req.add_header("anthropic-version", "2023-06-01")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def summarise(doc) -> str:
    if not isinstance(doc, dict):
        return str(doc)[:120]
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    usage = doc.get("usage") or {}
    return "text=%r tool_use=%d out_tokens=%s stop=%s" % (
        texts[:70], len(tuses), usage.get("output_tokens"), doc.get("stop_reason"))


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")
    messages = [{"role": "user", "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}]

    try:
        import wtoken_model_agent as agent_mod
        system_prompt = agent_mod.SYSTEM_PROMPT
        tools = agent_mod.TOOLS
        print("loaded SYSTEM_PROMPT (%d chars) and TOOLS (%d entries) from the agent"
              % (len(system_prompt), len(tools)))
    except Exception as exc:  # noqa: BLE001
        print("could not import the agent module:", exc)
        system_prompt = "You are a coding agent."
        tools = []

    cases = [
        ("bare: model+max_tokens+messages", {"model": "claude-opus-5", "max_tokens": 32000, "messages": messages}),
        ("+ system", {"model": "claude-opus-5", "max_tokens": 32000, "system": system_prompt, "messages": messages}),
        ("+ tools", {"model": "claude-opus-5", "max_tokens": 32000, "messages": messages, "tools": tools}),
        ("+ system + tools (agent-exact)", {"model": "claude-opus-5", "max_tokens": 32000, "system": system_prompt, "messages": messages, "tools": tools}),
    ]

    for label, payload in cases:
        t0 = time.time()
        status, doc = post(url, key, payload)
        secs = time.time() - t0
        if status != 200:
            print("  %-34s -> HTTP %s  %.1fs  %s" % (label, status, secs, str(doc)[:100]))
        else:
            print("  %-34s -> 200  %.1fs  %s" % (label, secs, summarise(doc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
