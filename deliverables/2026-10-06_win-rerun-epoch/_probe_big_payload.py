import json, sys, urllib.request, urllib.error

KEY = "sk-ff432bac0d50207c49ea61f7df586d5c003332dea2e4bb87826189e28db5ce4c"
URL = "https://api.ebondai.com/v1/messages"
REPEAT = int(sys.argv[1]) if len(sys.argv) > 1 else 1

TOOLS = [
    {"name": "read_file", "description": "Read a file",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write a file",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
]
BIG = "In a distant kingdom there lived a dragon. " * 1200  # ~50KB user payload

for i in range(REPEAT):
    body = json.dumps({
        "model": "claude-opus-5", "max_tokens": 64000,
        "system": "You are an expert Windows PowerShell engineer. Follow the contract strictly.",
        "tools": TOOLS,
        "messages": [{"role": "user", "content": BIG + "\n\nNow reply with exactly: PONG"}],
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read())
            print(f"#{i+1} HTTP 200 stop={d.get('stop_reason')} text={d['content'][0]['text'][:30]!r}")
    except urllib.error.HTTPError as e:
        print(f"#{i+1} HTTP {e.code} {e.read()[:160]!r}")
