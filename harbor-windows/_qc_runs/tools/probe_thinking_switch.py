"""探测任意模型端点是否支持关闭 thinking（`extra_body`）。

用法：
    python probe_thinking_switch.py GLM [OPUS KIMI QWEN]

对每个别名分别发两次相同的复杂请求（写代码，能触发 thinking）：
  1. baseline            —— 不传任何 extra
  2. thinking-disabled   —— 传 {"thinking":{"type":"disabled"}}

若第 2 次的 thinking 块归零且耗时显著下降，说明该端点支持，可写入
`<ALIAS>_EXTRA_JSON`（与仓库既有 KIMI 配置同写法）。脚本不打印密钥明文。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables"
                r"\2026-10-04_outside-harbor-win\runner\.env.local")
PROMPT = ("Write a complete Python module implementing CRC32 from scratch, "
          "with at least 30 lines of explanatory comments. Output code only.")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def headers_for(env: dict[str, str], alias: str) -> dict[str, str]:
    key = env.get(f"{alias}_API_KEY", "")
    auth = (env.get(f"{alias}_AUTH") or "x-api-key").strip().lower()
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    if auth == "authorization":
        headers["authorization"] = f"Bearer {key}"
    else:
        headers["x-api-key"] = key
    return headers


def call(env: dict[str, str], alias: str, label: str, extra: dict | None,
         max_tokens: int, timeout: int) -> None:
    base = env[f"{alias}_BASE_URL"].rstrip("/")
    url = base + "/v1/messages"
    model = env[f"{alias}_MODEL"]
    body: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    if extra:
        body.update(extra)
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers_for(env, alias), method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            doc = json.loads(response.read().decode("utf-8"))
        elapsed = time.time() - started
        blocks = doc.get("content") or []
        kinds = [b.get("type") for b in blocks if isinstance(b, dict)]
        thinking = "".join(b.get("thinking", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "thinking")
        text = "".join(b.get("text", "") for b in blocks
                       if isinstance(b, dict) and b.get("type") == "text")
        usage = doc.get("usage") or {}
        print(f"  {label:<20} OK   {elapsed:7.1f}s  blocks={kinds}  "
              f"thinking_chars={len(thinking)}  text_chars={len(text)}  "
              f"out={usage.get('output_tokens')}  stop={doc.get('stop_reason')}", flush=True)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        print(f"  {label:<20} HTTP {exc.code}  {time.time() - started:7.1f}s  {detail}", flush=True)
    except Exception as exc:  # noqa: BLE001 - network layer
        print(f"  {label:<20} {type(exc).__name__}  {time.time() - started:7.1f}s  {exc}", flush=True)


def main() -> int:
    aliases = [a.upper() for a in sys.argv[1:]] or ["GLM"]
    env = load_env(ENV_FILE)
    for alias in aliases:
        if f"{alias}_BASE_URL" not in env:
            print(f"!! {alias} 未在 .env.local 配置", flush=True)
            continue
        print(f"=== {alias}  model={env[f'{alias}_MODEL']}  "
              f"url={env[f'{alias}_BASE_URL']} ===", flush=True)
        call(env, alias, "baseline", None, 4096, 300)
        call(env, alias, "thinking-disabled", {"thinking": {"type": "disabled"}}, 4096, 300)
        print(flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
