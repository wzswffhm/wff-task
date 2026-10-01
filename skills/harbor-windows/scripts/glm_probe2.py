# -*- coding: utf-8 -*-
"""glm_probe2.py —— 判定 GLM-5.3 是否「结构性无法在 agent 链路中产出工具调用」

背景：GLM-5.3 在 agent 模式下每一步都出现 `content=0` / `finish_reason=length`，
thinking 字符数 ~97K，正文永远为空。此前已排除：
  - 鉴权（Authorization Bearer 可用）
  - 模型 id（小写连字符 glm-5.3 才有效）
  - 流式解析（改用 SSE 后仍无正文）
  - budget_tokens 生效（两条协议均被忽略）

本探针用**真实 agent 第一步**（system + instruction + tools），把 max_tokens 拉到
65536，看 GLM 能否在预算充足时吐出 text 或 tool_use。用于把结论落到
「模型自身能力失败」还是「端点/配置缺陷」。
"""

import json
import os
import time

import httpx

BASE = "https://ark.cn-beijing.volces.com/api/coding"
KEY = os.environ.get("ARK_KEY", "ark-9bd32e64-24a6-4df0-9e63-fa8e81ec6ad8-b750b")
TASK = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wsync-142"

import sys
sys.path.insert(0, r"C:\Users\Administrator\Desktop\wff-task\skills\harbor-windows\scripts")
import agent_harness

instruction = open(os.path.join(TASK, "instruction.md"), encoding="utf-8").read()

CASES = [
    # (标签, max_tokens, extra_body)
    ("max65536_no_thinking_field", 65536, None),
    ("max65536_thinking_disabled", 65536, {"thinking": {"type": "disabled"}}),
]

headers = {"authorization": "Bearer " + KEY,
           "anthropic-version": "2023-06-01",
           "content-type": "application/json"}

for label, mt, extra in CASES:
    payload = {
        "model": "glm-5.3",
        "max_tokens": mt,
        "system": agent_harness.system_prompt(),
        "messages": [{"role": "user",
                      "content": "## 任务\n\n" + instruction.strip() + "\n\n请开始。"}],
        "tools": agent_harness.TOOLS,
    }
    if extra:
        payload.update(extra)

    print("=" * 70)
    print("CASE %s  max_tokens=%d  extra=%s" % (label, mt, extra))
    t0 = time.time()
    try:
        status, doc, raw = agent_harness._post(BASE.rstrip("/") + "/v1/messages",
                                               headers, payload, timeout=1800)
    except Exception as e:
        print("  异常 %s: %s (%.1fs)" % (type(e).__name__, str(e)[:200], time.time() - t0))
        continue

    el = time.time() - t0
    if status != 200 or doc is None:
        print("  HTTP %s @%.1fs  body=%s" % (status, el, (raw or "")[:400]))
        continue

    blocks = doc.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    think = "".join(b.get("thinking", "") for b in blocks if b.get("type") == "thinking")
    tus = [b for b in blocks if b.get("type") == "tool_use"]
    print("  HTTP 200 @%.1fs  stop_reason=%s usage=%s" % (el, doc.get("stop_reason"), doc.get("usage")))
    print("  blocks=%s" % [b.get("type") for b in blocks])
    print("  text_len=%d  thinking_len=%d  tool_use=%d" % (len(text), len(think), len(tus)))
    if text:
        print("  text[:300]=%r" % text[:300])
    for b in tus:
        print("  tool_use: name=%s input_keys=%s" % (b.get("name"), list((b.get("input") or {}).keys())))
    print("  结论: %s" % ("可产出工具调用 → 属预算/配置问题"
                          if tus else "无任何 tool_use → 该模型无法在 agent 链路中工作"))
