import json, urllib.request, urllib.error

body = json.dumps({
    "model": "claude-opus-5", "max_tokens": 64000,
    "system": "You are an expert Windows PowerShell engineer.",
    "tools": [{"name": "read_file", "description": "Read a file",
               "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}],
    "messages": [{"role": "user", "content": "In a kingdom there lived a dragon. " * 800 + "\nReply with exactly: PONG"}],
}).encode()
req = urllib.request.Request("https://4router.net/v1/messages", data=body, method="POST", headers={
    "x-api-key": "sk-ABTdFUULEu52VnGHNhWQX8BA13uMpbPdTZZrogR5oGTla2gE", "anthropic-version": "2023-06-01",
    "content-type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
        print("HTTP 200 stop=", d.get("stop_reason"), "text=", d["content"][0]["text"][:20])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read()[:150])
