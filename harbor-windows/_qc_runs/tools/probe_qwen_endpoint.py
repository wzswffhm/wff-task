"""对比 QWEN 网关在不同 API key / model 下的响应情况（不写入任何跑分证据）。

背景：候选轮次自 12:52:58 起 95 分钟内零成功回合，全部模型调用以
``TimeoutError`` / ``RemoteDisconnected`` 失败。本脚本用极小请求区分三种可能：
  - key / 配额问题（当前 key 失效或被限流）
  - model 路由问题（qwen3.8-max-0902 拥堵，qwen3.7-plus 可用）
  - 整条网关故障

脚本不打印密钥明文，只回显掩码。
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


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def mask(key: str) -> str:
    if not key:
        return "(空)"
    return key[:12] + "..." + key[-6:] if len(key) > 24 else "***"


def probe(label: str, key: str, model: str, prompt: str,
          max_tokens: int, timeout: int) -> dict:
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "x-api-key": key,
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            doc = json.loads(response.read().decode("utf-8"))
        elapsed = time.time() - started
        blocks = doc.get("content") or []
        kinds = [b.get("type") for b in blocks if isinstance(b, dict)]
        text = "".join(b.get("text", "") for b in blocks
                       if isinstance(b, dict) and b.get("type") == "text")
        thinking = "".join(b.get("thinking", "") for b in blocks
                           if isinstance(b, dict) and b.get("type") == "thinking")
        usage = doc.get("usage") or {}
        print(f"{label:<10} {model:<18} OK    {elapsed:6.1f}s  blocks={kinds} "
              f"text={text.strip()[:32]!r} thinking_chars={len(thinking)} "
              f"out_tokens={usage.get('output_tokens')} stop={doc.get('stop_reason')}",
              flush=True)
        return {"ok": True, "seconds": elapsed, "usage": usage}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:220]
        print(f"{label:<10} {model:<18} HTTP {exc.code}  {time.time() - started:6.1f}s  {detail}",
              flush=True)
        return {"ok": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001 - network layer
        print(f"{label:<10} {model:<18} {type(exc).__name__}  {time.time() - started:6.1f}s  {exc}",
              flush=True)
        return {"ok": False, "error": type(exc).__name__}


def main() -> int:
    env = load_env(ENV_FILE)
    current_key = env.get("QWEN_API_KEY", "")
    new_key = os.environ.get("PROBE_QWEN_KEY", "")
    if not current_key:
        print("!! .env.local 里没有 QWEN_API_KEY")
        return 2

    print(f"端点      : {ENDPOINT}")
    print(f"当前 key  : {mask(current_key)}")
    print(f"新   key  : {mask(new_key)}")
    print(flush=True)

    cases = [("当前key", current_key, "qwen3.8-max-0902")]
    if new_key:
        cases += [("新key", new_key, "qwen3.8-max-0902"),
                  ("新key", new_key, "qwen3.7-plus")]

    print("=== 小请求（max_tokens=64，单次超时 150s）===")
    for label, key, model in cases:
        probe(label, key, model, "Reply with exactly one word: ok", 64, 150)

    if os.environ.get("PROBE_THROUGHPUT") == "1":
        print()
        print("=== 吞吐测试（max_tokens=2048，单次超时 900s）===")
        for label, key, model in cases:
            probe(label, key, model,
                  "Write a Python function computing CRC32 of bytes, with 20 lines of comments. Code only.",
                  2048, 900)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
