"""测试 GLM（火山引擎 ARK /api/coding）是否支持限制 thinking 预算。

`{"thinking":{"type":"disabled"}}` 已被端点以 HTTP 400 拒绝
（"thinking.type `disabled` is not supported by this model"），
因此转而测试能否用 budget_tokens 约束 thinking 长度，或改用 auto。
判定标准：thinking_chars 明显下降且 text_chars > 0（正文不再被吃空）。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables"
                r"\2026-10-04_outside-harbor-win\runner\.env.local")
PROMPT = ("Write a complete Python module implementing CRC32 from scratch, "
          "with at least 30 lines of explanatory comments. Output code only.")

CASES: list[tuple[str, dict | None]] = [
    ("baseline (max_tokens=16384)", None),
    ("thinking.enabled budget=2048", {"thinking": {"type": "enabled", "budget_tokens": 2048}}),
    ("thinking.auto", {"thinking": {"type": "auto"}}),
    ("thinking.enabled budget=8192", {"thinking": {"type": "enabled", "budget_tokens": 8192}}),
]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def main() -> int:
    env = load_env(ENV_FILE)
    url = env["GLM_BASE_URL"].rstrip("/") + "/v1/messages"
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "authorization": f"Bearer {env['GLM_API_KEY']}",
    }
    print(f"url={url}  model={env['GLM_MODEL']}", flush=True)
    for label, extra in CASES:
        body: dict = {
            "model": env["GLM_MODEL"],
            "max_tokens": 16384,
            "messages": [{"role": "user", "content": PROMPT}],
        }
        if extra:
            body.update(extra)
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                doc = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - started
            blocks = doc.get("content") or []
            kinds = [b.get("type") for b in blocks if isinstance(b, dict)]
            thinking = "".join(b.get("thinking", "") for b in blocks
                               if isinstance(b, dict) and b.get("type") == "thinking")
            text = "".join(b.get("text", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "text")
            usage = doc.get("usage") or {}
            print(f"  {label:<30} OK  {elapsed:7.1f}s  thinking={len(thinking):>6}字符  "
                  f"text={len(text):>5}字符  out={usage.get('output_tokens')}  "
                  f"stop={doc.get('stop_reason')}", flush=True)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            print(f"  {label:<30} HTTP {exc.code}  {time.time() - started:7.1f}s  {detail}",
                  flush=True)
        except Exception as exc:  # noqa: BLE001 - network layer
            print(f"  {label:<30} {type(exc).__name__}  {time.time() - started:7.1f}s  {exc}",
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
