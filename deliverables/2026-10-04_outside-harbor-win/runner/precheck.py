#!/usr/bin/env python3
"""Minimal connectivity precheck for every configured model endpoint.

Sends one tiny tool-calling request per alias and reports HTTP status plus the
first tool name the model chose. A failing alias is reported, not raised, so a
single broken endpoint cannot hide the state of the others.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


TOOL = [{
    "name": "ping",
    "description": "Reply with the word pong.",
    "input_schema": {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
    },
}]


def check(alias: str, env: dict[str, str]) -> str:
    prefix = f"{alias}_"
    base = env[prefix + "BASE_URL"].rstrip("/")
    url = base + "/v1/messages"
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if env.get(prefix + "AUTH", "x-api-key").lower() == "authorization":
        headers["authorization"] = "Bearer " + env[prefix + "API_KEY"]
    else:
        headers["x-api-key"] = env[prefix + "API_KEY"]
    body: dict = {
        "model": env[prefix + "MODEL"],
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "Call the ping tool with value 'pong'. Then say done."}],
        "tools": TOOL,
    }
    extra = env.get(prefix + "EXTRA_JSON")
    if extra:
        body.update(json.loads(extra))
    payload = json.dumps(body).encode()
    started = time.time()
    try:
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300].replace("\n", " ")
        return f"FAIL  HTTP {exc.code}  {detail}"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL  {type(exc).__name__}: {exc}"

    elapsed = time.time() - started
    names = [b.get("name") for b in data.get("content", []) if b.get("type") == "tool_use"]
    stop = data.get("stop_reason")
    return f"OK    {elapsed:5.1f}s  stop={stop}  tool_use={names or 'none'}"


def main() -> int:
    env = load_env(HERE / ".env.local")
    aliases = ["QWEN", "OPUS", "GLM", "KIMI"]
    failures = 0
    for alias in aliases:
        if not env.get(f"{alias}_BASE_URL"):
            print(f"{alias:<5} SKIP  (missing {alias}_BASE_URL)")
            continue
        line = check(alias, env)
        print(f"{alias:<5} {line}", flush=True)
        if line.startswith("FAIL"):
            failures += 1
    print()
    print(f"precheck: {len(aliases) - failures}/{len(aliases)} endpoints usable")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
