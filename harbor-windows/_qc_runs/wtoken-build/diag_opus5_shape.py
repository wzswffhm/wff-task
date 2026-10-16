"""Pin down exactly which request shape makes claude-opus-5 return the stub.

Previous run showed: bare request works; adding system OR tools returns
"⚠️ 上游模型未返回任何内容". But tools was an empty list there because the agent
module failed to import, so this nail down the boundaries:

  * system=None vs system="" vs system="x" vs absent
  * tools=[] vs tools=None vs absent vs one real tool
  * the same shapes against claude-opus-4-8 for contrast

Run: python diag_opus5_shape.py
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


def post(url: str, key: str, payload: dict, timeout: int = 90) -> tuple[int, object]:
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
        return "non-dict: " + str(doc)[:80]
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    usage = doc.get("usage") or {}
    stub = "上游模型未返回任何内容" in texts
    if stub:
        tag = "STUB"
    elif tuses:
        tag = "TOOL_USE"
    elif texts.strip():
        tag = "TEXT"
    else:
        tag = "EMPTY"
    return "%-9s tool_use=%d out=%-4s stop=%-10s %s" % (
        tag, len(tuses), usage.get("output_tokens"), doc.get("stop_reason"), texts[:40].replace("\n", " "))


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")
    messages = [{"role": "user", "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}]
    one_tool = [{"name": "run_command", "description": "run a shell command",
                 "input_schema": {"type": "object", "properties": {"command": {"type": "string"}},
                                  "required": ["command"]}}]

    for model in ("claude-opus-5", "claude-opus-4-8"):
        print("=== %s ===" % model)
        base = {"model": model, "max_tokens": 4000, "messages": messages}
        cases = [
            ("no system, no tools", dict(base)),
            ("system=None", dict(base, system=None)),
            ("system=''", dict(base, system="")),
            ("system='x'", dict(base, system="x")),
            ("tools=[]", dict(base, tools=[])),
            ("tools=None", dict(base, tools=None)),
            ("tools=1 real tool", dict(base, tools=one_tool)),
            ("system='x' + tools=[]", dict(base, system="x", tools=[])),
        ]
        for label, payload in cases:
            t0 = time.time()
            status, doc = post(url, key, payload)
            secs = time.time() - t0
            if status != 200:
                print("  %-26s HTTP %-3s %.1fs %s" % (label, status, secs, str(doc)[:70]))
            else:
                print("  %-26s %.1fs %s" % (label, secs, verdict(doc)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
