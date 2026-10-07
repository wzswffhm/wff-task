#!/usr/bin/env python
"""探测 ebondai(claude-opus-5) 中转的保真度：
1) usage 字段是否真实（input_tokens 是否被伪造成 1/2）
2) 是否支持**并行工具调用**（同一 assistant 回合返回多个 tool_use）
3) 是否默认开启 thinking，thinking 是否计入 output_tokens
"""
import json
import time
import urllib.request

BASE = "https://api.ebondai.com"
KEY = "sk-e01ac61f23d90990a5672e5fa22806fc5890684d7f4acbd3209ca96d4b60a208"
MODEL = "claude-opus-5"

TOOLS = [
    {
        "name": "read_file",
        "description": "读取一个文件的内容。",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件路径"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "列出一个目录下的文件。",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "目录路径"}},
            "required": ["path"],
        },
    },
]


def call(payload, timeout=180):
    req = urllib.request.Request(
        BASE + "/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-api-key": KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    return r.status, json.loads(body), time.time() - t0


def report(tag, status, doc, dt):
    print("===== %s =====" % tag)
    print("  http=%s elapsed=%.1fs" % (status, dt))
    print("  usage=%s" % json.dumps(doc.get("usage"), ensure_ascii=False))
    print("  stop_reason=%s" % doc.get("stop_reason"))
    blocks = doc.get("content") or []
    kinds = [b.get("type") for b in blocks]
    print("  blocks=%s" % kinds)
    tus = [b for b in blocks if b.get("type") == "tool_use"]
    print("  tool_use_count=%d" % len(tus))
    for b in tus:
        print("     - %s %s" % (b.get("name"), json.dumps(b.get("input"), ensure_ascii=False)[:90]))
    texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    if texts:
        print("  text=%s" % ("\n".join(texts))[:400])


# --- 1) 简单请求：usage 真伪 ---
try:
    st, doc, dt = call({
        "model": MODEL, "max_tokens": 256,
        "messages": [{"role": "user", "content": "只回复两个字：好的"}],
    })
    report("A. 简单对话", st, doc, dt)
except Exception as e:
    print("A 失败:", type(e).__name__, e)
    try:
        print("   body:", e.read().decode("utf-8")[:600])
    except Exception:
        pass

# --- 2) 并行工具调用 ---
PROMPT = (
    "请立刻并行执行下面两个工具调用（同一个回合里同时给出），不要先看结果：\n"
    "1) read_file(path='wtask/duration.py')\n"
    "2) list_files(path='wtask')\n"
    "只需发出这两个 tool_use，不要输出多余文字。"
)
try:
    st, doc, dt = call({
        "model": MODEL, "max_tokens": 1024,
        "tools": TOOLS,
        "messages": [{"role": "user", "content": PROMPT}],
    })
    report("B. 并行工具调用", st, doc, dt)
except Exception as e:
    print("B 失败:", type(e).__name__, e)
    try:
        print("   body:", e.read().decode("utf-8")[:600])
    except Exception:
        pass

# --- 3) 显式关闭 thinking ---
try:
    st, doc, dt = call({
        "model": MODEL, "max_tokens": 512,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": "回复：ok"}],
    })
    report("C. thinking=disabled", st, doc, dt)
except Exception as e:
    print("C 失败:", type(e).__name__, e)
    try:
        print("   body:", e.read().decode("utf-8")[:600])
    except Exception:
        pass
