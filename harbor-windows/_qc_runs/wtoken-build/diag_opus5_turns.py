"""Test whether the upstream stub is triggered by tool_result turns.

Evidence: with the system field removed, claude-opus-5 successfully produced a
tool_use turn (list_files), but the very next request — whose messages now carry
the assistant tool_use turn plus a user tool_result turn — came back as the stub.
This script walks the conversation forward one turn at a time to find the exact
message shape that flips it.

Run: python diag_opus5_turns.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wtoken-221-v1.0.0-delivery"


def load_endpoint() -> dict:
    cfg = json.loads((ROOT / "models.local.json").read_text(encoding="utf-8"))
    for item in cfg["endpoints"]:
        if item.get("key") == "opus-5":
            return item
    raise SystemExit("opus-5 endpoint not found")


def post(url: str, key: str, payload: dict, timeout: int = 120):
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


def verdict(doc) -> str:
    if not isinstance(doc, dict):
        return "non-dict " + str(doc)[:70]
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    usage = doc.get("usage") or {}
    if "上游模型未返回任何内容" in texts:
        tag = "STUB"
    elif tuses:
        tag = "TOOL_USE(" + ",".join(t.get("name", "?") for t in tuses) + ")"
    elif texts.strip():
        tag = "TEXT"
    else:
        tag = "EMPTY"
    return "%-22s out=%-5s stop=%-10s %s" % (tag, usage.get("output_tokens"),
                                             doc.get("stop_reason"), texts[:50].replace("\n", " "))


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")

    tools = [{
        "name": "list_files",
        "description": "List files under a directory",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                         "required": ["path"]},
    }]

    first_user = {"role": "user", "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}
    tool_use = {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_01", "name": "list_files",
         "input": {"path": "."}}]}
    tool_result = {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_01",
         "content": "README.md\nwtoken/__init__.py\ntests/"}]}

    stages = [
        ("turn1: user only", [first_user]),
        ("turn2: + assistant tool_use", [first_user, tool_use]),
        ("turn3: + tool_result", [first_user, tool_use, tool_result]),
        ("turn3b: tool_result as text", [first_user, tool_use,
                                         {"role": "user", "content": "README.md\nwtoken/__init__.py\ntests/"}]),
        ("turn3c: tool_use dropped, plain text", [first_user,
                                                  {"role": "assistant", "content": "I will list files."},
                                                  {"role": "user", "content": "README.md\nwtoken/__init__.py"}]),
    ]

    for label, messages in stages:
        payload = {"model": "claude-opus-5", "max_tokens": 4000, "messages": messages, "tools": tools}
        t0 = time.time()
        status, doc = post(url, key, payload)
        secs = time.time() - t0
        if status != 200:
            print("  %-34s HTTP %-3s %.1fs %s" % (label, status, secs, str(doc)[:60]))
        else:
            print("  %-34s %.1fs %s" % (label, secs, verdict(doc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
