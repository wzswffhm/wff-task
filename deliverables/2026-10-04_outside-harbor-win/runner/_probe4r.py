import json, time, urllib.request, urllib.error

BASE = "https://4router.net"
KEY = "sk-ABTdFUULEu52VnGHNhWQX8BA13uMpbPdTZZrogR5oGTla2gE"
HDRS = {
    "content-type": "application/json",
    "anthropic-version": "2023-06-01",
    "x-api-key": KEY,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}


def post(path, body, headers=None, timeout=180, stream=False):
    h = dict(HDRS)
    if stream:
        h["accept"] = "text/event-stream"
    if headers:
        h.update(headers)
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=h, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if stream:
                chunks = []
                for raw in r:
                    chunks.append(raw)
                return {"ok": True, "elapsed": round(time.time() - t0, 1), "nbytes": sum(len(c) for c in chunks),
                        "head": b"".join(chunks[:8]).decode("utf-8", "replace")[:600]}
            raw = r.read()
            return {"ok": True, "elapsed": round(time.time() - t0, 1), "status": r.status,
                    "body": raw.decode("utf-8", "replace")[:600]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "elapsed": round(time.time() - t0, 1), "http": e.code,
                "detail": e.read().decode("utf-8", "replace")[:600]}
    except Exception as e:
        return {"ok": False, "elapsed": round(time.time() - t0, 1), "err": f"{type(e).__name__}: {e}"}


TOOLS = [{
    "name": "finish",
    "description": "Signal completion.",
    "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": []},
}]

out = {}
# 1. minimal non-stream
out["1_nonstream_small"] = post("/v1/messages", {
    "model": "claude-opus-5", "max_tokens": 64,
    "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
}, timeout=120)
# 2. tool use non-stream
out["2_nonstream_tools"] = post("/v1/messages", {
    "model": "claude-opus-5", "max_tokens": 512,
    "messages": [{"role": "user", "content": "Call the finish tool with summary='hi'."}],
    "tools": TOOLS,
}, timeout=180)
# 3. streaming
out["3_stream"] = post("/v1/messages", {
    "model": "claude-opus-5", "max_tokens": 512, "stream": True,
    "messages": [{"role": "user", "content": "Call the finish tool with summary='hi'."}],
    "tools": TOOLS,
}, timeout=180, stream=True)
# 4. big max_tokens streaming (balance probe)
out["4_stream_big"] = post("/v1/messages", {
    "model": "claude-opus-5", "max_tokens": 32000, "stream": True,
    "messages": [{"role": "user", "content": "Write a long essay about the history of computing, at least 3000 words."}],
}, timeout=600, stream=True)

with open("logs/_probe4r.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
for k, v in out.items():
    print(k, "->", json.dumps(v, ensure_ascii=False)[:300])
