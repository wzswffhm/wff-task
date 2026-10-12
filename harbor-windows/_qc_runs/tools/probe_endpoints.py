"""探测四个模型端点的即时可用性（极小请求，不写入任何跑分证据）。

用途：QWEN 轮次出现连续 model call 超时（TimeoutError / RemoteDisconnected）时，
区分是"端点整体故障"还是"长上下文导致单次生成过慢"。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner\.env.local")


def load_env(path: Path) -> dict:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def main() -> int:
    env = load_env(ENV)
    for alias in ("QWEN", "OPUS", "GLM", "KIMI"):
        prefix = alias + "_"
        base = env.get(prefix + "BASE_URL")
        key = env.get(prefix + "API_KEY")
        model = env.get(prefix + "MODEL")
        auth = (env.get(prefix + "AUTH") or "x-api-key").lower()
        if not (base and key and model):
            print(f"{alias:<5} 配置缺失", flush=True)
            continue
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }
        if auth == "authorization":
            headers["authorization"] = "Bearer " + key
        else:
            headers["x-api-key"] = key
        body = {
            "model": model,
            "max_tokens": 24,
            "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
        }
        request = urllib.request.Request(
            base.rstrip("/") + "/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                doc = json.loads(response.read().decode("utf-8"))
            text = "".join(b.get("text", "") for b in doc.get("content", []) if isinstance(b, dict))
            print(f"{alias:<5} OK   {time.time() - started:6.1f}s  model={model}  "
                  f"reply={text.strip()[:30]!r}", flush=True)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:180]
            print(f"{alias:<5} HTTP {exc.code}  {time.time() - started:6.1f}s  {detail}", flush=True)
        except Exception as exc:  # noqa: BLE001 - network layer
            print(f"{alias:<5} {type(exc).__name__}  {time.time() - started:6.1f}s  {exc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
