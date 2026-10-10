"""量化 QWEN 网关的生成吞吐与长输入处理耗时（不写入任何跑分证据）。

背景：小请求 2.4s 正常，但 runner 的真实请求连续 5 次吃满 QWEN_REQUEST_TIMEOUT=900
超时。本脚本把两类开销拆开测：
  A. 短输入 + 长输出 —— 测纯生成吞吐（tokens/s），用于推算 QWEN_MAX_TOKENS=65536 的耗时
  B. 长输入 + 短输出 —— 测长上下文的处理耗时（输入用真实 agent.log 内容）
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
AGENT_LOG = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables"
                 r"\2026-10-04_outside-harbor-win\runner\runs\wfflab__wchunk-216"
                 r"\20261010T122847-candidate-qwen3.8-max-0902-01-9d6b"
                 r"\qwen3.8-max-0902\agent.log")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def call(key: str, model: str, system: str, prompt: str,
         max_tokens: int, timeout: int) -> None:
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "x-api-key": key,
    }
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            doc = json.loads(response.read().decode("utf-8"))
        elapsed = time.time() - started
        usage = doc.get("usage") or {}
        out = usage.get("output_tokens") or 0
        rate = f"{out / elapsed:6.1f} tok/s" if elapsed > 0 and out else "      -"
        print(f"OK    {elapsed:7.1f}s  in={usage.get('input_tokens')} out={out}  {rate}  "
              f"stop={doc.get('stop_reason')}", flush=True)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        print(f"HTTP {exc.code}  {time.time() - started:7.1f}s  {detail}", flush=True)
    except Exception as exc:  # noqa: BLE001 - network layer
        print(f"{type(exc).__name__}  {time.time() - started:7.1f}s  {exc}", flush=True)


def main() -> int:
    env = load_env(ENV_FILE)
    key = os.environ.get("PROBE_QWEN_KEY") or env.get("QWEN_API_KEY", "")
    model = os.environ.get("PROBE_QWEN_MODEL") or env.get("QWEN_MODEL", "qwen3.8-max-0902")
    log_text = AGENT_LOG.read_text(encoding="utf-8", errors="replace")
    system = ("You are a coding agent working inside a Windows container. "
              "Answer directly and concisely.")

    print(f"model={model}  端点={ENDPOINT}", flush=True)
    print(f"agent.log 长度={len(log_text)} 字符", flush=True)

    print("\nA. 短输入 + 长输出（max_tokens=8192，超时 900s）—— 测生成吞吐", flush=True)
    call(key, model, system, "Print the integers from 1 to 1200, one per line, nothing else.",
         8192, 900)

    print("\nB. 长输入 + 短输出（max_tokens=64，超时 600s）—— 测长上下文处理", flush=True)
    call(key, model, system,
         "以下是某次 agent 运行的日志片段：\n\n" + log_text + "\n\nReply with exactly: done",
         64, 600)

    print("\nC. 长输入 + 中等输出（max_tokens=1024，超时 900s）—— 最接近真实调用", flush=True)
    call(key, model, system,
         "以下是某次 agent 运行的日志片段：\n\n" + log_text
         + "\n\n用中文写 500 字总结这次运行做了什么。",
         1024, 900)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
