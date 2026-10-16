"""Find a system-prompt form the upstream will accept.

Evidence so far:
  * sending the `system` field        -> STUB
  * merging the Chinese SYSTEM_PROMPT -> stop_reason=refusal ("这条内容上游没有收下")
  * user message with only the 2413-char instruction -> works

So the prefix content matters. This tests several preambles ahead of the same
instruction to find one that is accepted, then the agent can inline that.

Run: python diag_opus5_system.py
"""

from __future__ import annotations

import json
import re
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


def post(url: str, key: str, payload: dict, timeout: int = 180):
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


def verdict(doc) -> tuple[str, str]:
    if not isinstance(doc, dict):
        return "ERROR", str(doc)[:50]
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    if "上游模型未返回任何内容" in texts:
        return "STUB", ""
    if "上游没有收下" in texts:
        return "REFUSAL", ""
    if tuses:
        return "TOOL_USE", ""
    if texts.strip():
        return "TEXT", texts[:40].replace("\n", " ")
    return "EMPTY", ""


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")

    src = (BUILD / "harbor_agent" / "wtoken_model_agent.py").read_text(encoding="utf-8")
    m = re.search(r'SYSTEM_PROMPT\s*=\s*\((.*?)\)\s*\n', src, re.S)
    original = ""
    if m:
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
        original = "".join(parts).encode().decode("unicode_escape")

    tools = [{"name": "list_files", "description": "List files under a directory",
              "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                               "required": ["path"]}}]

    english_short = ("You are an agent working on a Windows coding task. "
                     "Use the tools to inspect and edit files in the workspace. "
                     "Call submit when finished.")
    english_detailed = (
        "You are the execution agent for a Harbor Windows coding task.\n"
        "The workspace is mounted in the container; use the tools to browse, read and edit files.\n\n"
        "How to work:\n"
        "1. Use list_files to inspect the layout, then read_file for key sources.\n"
        "2. After locating the defect, use write_file with the complete fixed file content.\n"
        "3. Use run_command for one-off verification such as: python -m pytest tests/ -q\n"
        "4. Call submit when done and summarise the change.\n\n"
        "Constraints:\n"
        "- Only modify implementation code.\n"
        "- Do not create, modify or delete anything under tests/.\n"
        "- Leave no debug scripts or temporary files behind.\n"
        "- Do not touch paths outside the workspace.\n")

    cases = [
        ("instruction only (baseline)", instruction.strip() + "\n\n请开始。"),
        ("chinese SYSTEM_PROMPT + instruction", original.strip() + "\n\n## 任务\n\n" + instruction.strip()),
        ("english short + instruction", english_short + "\n\n" + instruction.strip()),
        ("english detailed + instruction", english_detailed + "\n\n## Task\n\n" + instruction.strip()),
        ("ascii marker + instruction", "=== system ===\n" + "You are a coding agent.\n" + "=== task ===\n" + instruction.strip()),
    ]

    for label, content in cases:
        payload = {"model": "claude-opus-5", "max_tokens": 32000,
                   "messages": [{"role": "user", "content": content}], "tools": tools}
        t0 = time.time()
        status, doc = post(url, key, payload)
        tag, extra = verdict(doc) if status == 200 else ("HTTP %s" % status, "")
        print("  %-40s %6.1fs  %-10s %s" % (label, time.time() - t0, tag, extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
