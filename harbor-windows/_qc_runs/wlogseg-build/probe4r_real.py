# -*- coding: utf-8 -*-
"""probe4r_real.py —— 用**真实负载**（218 题面 + 完整工具集）探 4router 端点。

短请求探活绿不代表真实负载可用：本次故障正是「小请求秒回、真实负载挂起」。
判定口径：每次请求给 wall=180s 墙钟；记录总时长、stop_reason、tool_use、output_tokens。

用法：
    python -u probe4r_real.py [--n 3] [--wall 180] [--max-tokens 32000]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

ROOT = r"C:\Users\Administrator\Desktop\wff-task"
SKILL_SCRIPTS = os.path.join(ROOT, "harbor-windows", "skills", "harbor-windows", "scripts")
PKG = os.path.join(ROOT, "harbor-windows", "wfflab__wlogseg-218-v1.0.0-delivery")
CFG = os.path.join(os.environ.get("TEMP", "/tmp"), "wff-opus4router.endpoints.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--wall", type=float, default=180.0)
    ap.add_argument("--max-tokens", type=int, default=32000)
    a = ap.parse_args()

    sys.path.insert(0, SKILL_SCRIPTS)
    import agent_harness as ah  # noqa: E402

    cfg = json.load(io.open(CFG, encoding="utf-8"))
    ep = cfg["endpoints"][0]
    instr = io.open(os.path.join(PKG, "instruction.md"), encoding="utf-8").read()

    url = ep["base_url"].rstrip("/") + "/v1/messages"
    headers = {"anthropic-version": "2023-06-01", "content-type": "application/json",
               "x-api-key": ep["api_key"]}
    payload = {
        "model": ep["model"],
        "max_tokens": a.max_tokens,
        "system": ah.system_prompt(),
        "messages": [{"role": "user", "content": "## 任务\n\n" + instr.strip() + "\n\n请开始。"}],
        "tools": ah.TOOLS,
    }
    print("payload 估算：instruction %d 字符 / tools %d 个 / max_tokens=%d / wall=%.0fs"
          % (len(instr), len(ah.TOOLS), a.max_tokens, a.wall), flush=True)

    ok = 0
    for i in range(1, a.n + 1):
        t0 = time.time()
        try:
            status, doc, raw = ah._post(url, headers, payload, timeout=a.wall)
        except Exception as e:  # noqa: BLE001
            print("%d) FAIL %s: %s  (%.1fs)"
                  % (i, type(e).__name__, str(e)[:200], time.time() - t0), flush=True)
            continue
        dt = time.time() - t0
        if status != 200 or doc is None:
            print("%d) HTTP %s (%.1fs) %s" % (i, status, dt, (raw or "")[:200]), flush=True)
            continue
        names = [b.get("name") for b in (doc.get("content") or []) if b.get("type") == "tool_use"]
        texts = "".join(b.get("text") or "" for b in (doc.get("content") or [])
                        if b.get("type") == "text")
        usage = doc.get("usage") or {}
        empty = ah._upstream_unavailable(doc)
        verdict = "OK" if not empty else "PSEUDO(%s)" % empty
        print("%d) %s %.1fs stop=%s tool_use=%s out_tokens=%s text=%r"
              % (i, verdict, dt, doc.get("stop_reason"), names,
                 usage.get("output_tokens"), texts[:100]), flush=True)
        if not empty:
            ok += 1
        if i < a.n:
            time.sleep(5)
    print("有效响应 %d/%d" % (ok, a.n))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
