"""验证 QWEN 网关是否支持关闭 thinking（`extra_body` 的两种写法）。

如果支持，就能在保留完整输出能力的前提下根除「thinking 过长 → 900s 读超时」，
比单纯压低 max_tokens 更优。脚本不打印密钥明文。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = ("https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com"
            "/apps/anthropic/v1/messages")
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


def call(key: str, label: str, extra: dict | None, max_tokens: int = 8192,
         timeout: int = 900) -> None:
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "x-api-key": key,
    }
    body: dict = {
        "model": "qwen3.8-max-0902",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    if extra:
        body.update(extra)
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            doc = json.loads(response.read().decode("utf-8"))
        elapsed = time.time() - started
        blocks = doc.get("content") or []
        kinds = [b.get("type") for b in blocks if isinstance(b, dict)]
        thinking = "".join(b.get("thinking", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "thinking")
        usage = doc.get("usage") or {}
        out = usage.get("output_tokens") or 0
        print(f"{label:<34} OK   {elapsed:7.1f}s  blocks={kinds}  thinking_chars={len(thinking)}  "
              f"out={out}  {out / elapsed if elapsed else 0:5.1f} tok/s  stop={doc.get('stop_reason')}",
              flush=True)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:240]
        print(f"{label:<34} HTTP {exc.code}  {time.time() - started:7.1f}s  {detail}", flush=True)
    except Exception as exc:  # noqa: BLE001 - network layer
        print(f"{label:<34} {type(exc).__name__}  {time.time() - started:7.1f}s  {exc}", flush=True)


def main() -> int:
    env = load_env(ENV_FILE)
    key = os.environ.get("PROBE_QWEN_KEY") or env.get("QWEN_API_KEY", "")
    print("对照组（不关闭 thinking）", flush=True)
    call(key, "baseline", None)
    print("\n写法 1：thinking.type=disabled", flush=True)
    call(key, "thinking-disabled", {"thinking": {"type": "disabled"}})
    print("\n写法 2：enable_thinking=false", flush=True)
    call(key, "enable_thinking-false", {"enable_thinking": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
