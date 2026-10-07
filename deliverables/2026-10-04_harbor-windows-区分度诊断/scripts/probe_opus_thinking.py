#!/usr/bin/env python
"""测试 ebondai Opus 的 thinking 配置：默认 / enabled+预算 / disabled，均带 tools。"""
import json
import time
import urllib.request

BASE = "https://api.ebondai.com"
KEY = "sk-e01ac61f23d90990a5672e5fa22806fc5890684d7f4acbd3209ca96d4b60a208"
MODEL = "claude-opus-5"

TOOLS = [{
    "name": "run_command",
    "description": "在工作区执行一条命令。",
    "input_schema": {"type": "object",
                     "properties": {"command": {"type": "string"}},
                     "required": ["command"]},
}]

PROMPT = (
    "任务：wtask 引擎里「周重复」触发器的语义是——以 StartBoundary 所在自然周为锚，"
    "每 WeeksInterval 周触发一次，且 `<Week>` 若为 5 表示当月最后一周。\n"
    "现在有一个 bug：`_week_index` 用了 `day.day // 7 + 1` 而不是 `(day.day - 1)//7 + 1`。\n"
    "请先说明正确的周序号公式（1-5），然后用 run_command 执行一条 python -c 验证 2026-03-31 属于第几周，"
    "最后给出结论。"
)


def call(payload, timeout=300):
    req = urllib.request.Request(
        BASE + "/v1/messages",
        data=json.dumps(payload).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode()), time.time() - t0


CASES = [
    ("默认（不传 thinking）", {}),
    ("thinking=enabled budget=8000", {"thinking": {"type": "enabled", "budget_tokens": 8000}}),
    ("thinking=enabled budget=2000", {"thinking": {"type": "enabled", "budget_tokens": 2000}}),
]

for label, extra in CASES:
    payload = {"model": MODEL, "max_tokens": 16000, "tools": TOOLS,
               "messages": [{"role": "user", "content": PROMPT}]}
    payload.update(extra)
    print("========== %s ==========" % label)
    try:
        st, doc, dt = call(payload)
        u = doc.get("usage") or {}
        print("  http=%s %.1fs stop=%s out=%s thinking=%s" % (
            st, dt, doc.get("stop_reason"), u.get("output_tokens"),
            (u.get("output_tokens_details") or {}).get("thinking_tokens")))
        blocks = doc.get("content") or []
        print("  block_types=%s" % [b.get("type") for b in blocks])
        for b in blocks:
            if b.get("type") == "thinking":
                print("  thinking_head=%s" % (b.get("thinking", "")[:160].replace("\n", " ")))
            if b.get("type") == "text":
                print("  text=%s" % (b.get("text", "")[:400].replace("\n", " | ")))
            if b.get("type") == "tool_use":
                print("  tool=%s %s" % (b.get("name"), json.dumps(b.get("input"), ensure_ascii=False)[:120]))
    except Exception as e:
        print("  FAILED: %s %s" % (type(e).__name__, e))
        try:
            print("   body:", e.read().decode()[:400])
        except Exception:
            pass
    print()
