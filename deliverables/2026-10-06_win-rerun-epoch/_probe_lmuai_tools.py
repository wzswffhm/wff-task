import json
import urllib.request
import urllib.error

KEY = "sk-391b43374428644458bc9a793af01d064d7a285fa7e9a00d4c92debd9e814321"
body = json.dumps({
    "model": "glm-5.3",
    "max_tokens": 512,
    "system": "You are an expert Windows PowerShell engineer. Use tools when asked.",
    "tools": [{
        "name": "read_file",
        "description": "Read a file from the workspace",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    }],
    "messages": [{"role": "user", "content": "Read the file C:\\task\\environment\\workspace\\README.md and then reply DONE."}],
}).encode()
req = urllib.request.Request("https://api.lmuai.com/v1/messages", data=body, method="POST", headers={
    "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
try:
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    print("stop=", d.get("stop_reason"))
    for blk in d.get("content", []):
        print(" block:", blk.get("type"), "|", json.dumps(blk.get("input") or blk.get("text", ""))[:160])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", "replace")[:250])
