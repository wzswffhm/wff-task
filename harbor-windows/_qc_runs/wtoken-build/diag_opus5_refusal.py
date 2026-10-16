"""Find which tool-output content triggers the upstream refusal.

Step 1 now succeeds after retries (the system/tool_result fixes work), but step 2
came back with stop_reason=refusal and the text "这条内容上游没有收下。请换一种
说法，或新开一个对话后再试。" — so the tool output itself is being rejected.

This walks the second turn with different observation contents to isolate what
the upstream objects to: the .git listing, the length, the Chinese brackets, etc.

Run: python diag_opus5_refusal.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wtoken-221-v1.0.0-delivery"

sys.path.insert(0, str(ROOT / "harbor-windows" / "_qc_runs" / "wtoken-build" / "harbor_agent"))


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
        return "ERROR", str(doc)[:60]
    blocks = doc.get("content") or []
    texts = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    tuses = [b for b in blocks if b.get("type") == "tool_use"]
    stop = doc.get("stop_reason") or "?"
    if "上游模型未返回任何内容" in texts:
        return "STUB", texts[:40]
    if "上游没有收下" in texts:
        return "REFUSAL", texts[:40]
    if tuses:
        return "TOOL_USE(" + ",".join(t.get("name", "?") for t in tuses) + ")", ""
    if texts.strip():
        return "TEXT", texts[:40].replace("\n", " ")
    return "EMPTY/" + stop, ""


def main() -> int:
    ep = load_endpoint()
    url = ep["base_url"].rstrip("/") + "/v1/messages"
    key = ep["api_key"]
    instruction = (PKG / "instruction.md").read_text(encoding="utf-8")

    tools = [{"name": "list_files", "description": "List files under a directory",
              "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                               "required": ["path"]}}]
    first_user = {"role": "user", "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}
    tool_use = {"role": "assistant", "content": [
        {"type": "tool_use", "id": "toolu_01", "name": "list_files", "input": {"path": "."}}]}

    git_listing = subprocess.run(["cmd", "/c", "dir", "/b", "/s", str(PKG)],
                                 capture_output=True, text=True, errors="replace").stdout[:8000]

    observations = [
        ("short chinese wrapper", "【工具 list_files 的输出】\nREADME.md\nwtoken/\ntests/"),
        ("plain short", "README.md\nwtoken/\ntests/"),
        ("git dir listing", ".git/COMMIT_EDITMSG\n.git/HEAD\n.git/config\n.git/description"),
        ("real dir /s /b output (truncated 8000)", git_listing),
        ("chinese prose only", "我列出了工作区的文件，包含 README、wtoken 包和测试目录。"),
        ("brackets only", "【】《》"),
    ]

    for label, obs in observations:
        messages = [first_user, tool_use, {"role": "user", "content": obs}]
        payload = {"model": "claude-opus-5", "max_tokens": 32000, "messages": messages, "tools": tools}
        t0 = time.time()
        status, doc = post(url, key, payload)
        tag, extra = verdict(doc) if status == 200 else ("HTTP %s" % status, "")
        print("  %-38s %6.1fs  %-24s %s" % (label, time.time() - t0, tag, extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
