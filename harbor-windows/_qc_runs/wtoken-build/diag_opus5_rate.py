"""Measure how often claude-opus-5 actually engages with the agent's exact payload.

The agent's payload after the fixes:
  * no `system` field (folded into the first user message)
  * tool output carried as plain text, never `tool_result` blocks

This replays that shape against the endpoint five times, twice: once with the
full instruction and a real tool list (what a round sends), and once walking two
turns (tool_use, then the plain-text tool output) to confirm the second turn also
survives. A high stub rate here means the endpoint itself is the bottleneck, not
the agent.

Run: python diag_opus5_rate.py
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


def load_endpoint() -> dict:
    cfg = json.loads((ROOT / "models.local.json").read_text(encoding="utf-8"))
    for item in cfg["endpoints"]:
        if item.get("key") == "opus-5":
            return item
    raise SystemExit("opus-5 endpoint not found")


def post(url: str, key: str, payload: dict, timeout: int = 150):
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
    except Exception as exc:  # noqa: BLE001
        return 0, "%s: %s" % (type(exc).__name__, exc)


def verdict(doc) -> tuple[str, int]:
    if not isinstance(doc, dict):
        return "ERROR", 0
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    usage = doc.get("usage") or {}
    out = usage.get("output_tokens") or 0
    if "上游模型未返回任何内容" in texts:
        return "STUB", out
    if tuses:
        return "TOOL_USE(" + ",".join(t.get("name", "?") for t in tuses) + ")", out
    if texts.strip():
        return "TEXT", out
    return "EMPTY", out


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")

    tools = [{
        "name": "list_files",
        "description": "List files under a directory",
        "input_schema": {"type": "object",
                         "properties": {"path": {"type": "string"}},
                         "required": ["path"]},
    }]
    first_user = {"role": "user",
                  "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}

    print("=== five single-turn attempts (agent payload shape) ===")
    ok = 0
    for i in range(1, 6):
        payload = {"model": "claude-opus-5", "max_tokens": 32000,
                   "messages": [first_user], "tools": tools}
        t0 = time.time()
        status, doc = post(url, key, payload)
        tag, out = verdict(doc) if status == 200 else ("HTTP %s" % status, 0)
        if tag.startswith("TOOL_USE"):
            ok += 1
        print("  #%d  %5.1fs  %-24s out=%s" % (i, time.time() - t0, tag, out))
    print("  engaged %d/5" % ok)

    print()
    print("=== two-turn walkthrough (tool_use then plain-text output) ===")
    tool_use = {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_01", "name": "list_files", "input": {"path": "."}}]}
    plain = {"role": "user", "content": "【工具 list_files 的输出】\nREADME.md\nwtoken/"}
    payload = {"model": "claude-opus-5", "max_tokens": 32000,
               "messages": [first_user, tool_use, plain], "tools": tools}
    t0 = time.time()
    status, doc = post(url, key, payload)
    tag, out = verdict(doc) if status == 200 else ("HTTP %s" % status, 0)
    print("  turn 3  %5.1fs  %-24s out=%s" % (time.time() - t0, tag, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
