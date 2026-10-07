# -*- coding: utf-8 -*-
"""探测 4router 大 payload 下是否挂起（模拟 run03 turn5 的大上下文）"""
import json, sys, time, urllib.request, urllib.error

KEY = "sk-ABTdFUULEu52VnGHNhWQX8BA13uMpbPdTZZrogR5oGTla2gE"
URL = "https://4router.net/v1/messages"

n_reps = int(sys.argv[1]) if len(sys.argv) > 1 else 4000   # ~170KB
tries  = int(sys.argv[2]) if len(sys.argv) > 2 else 2
timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 90

content = ("Audit log fragment: " + "In a kingdom there lived a dragon. " * n_reps
           + "\n\nReply with exactly: PONG")

body = json.dumps({
    "model": "claude-opus-5", "max_tokens": 4096,
    "system": "You are an expert Windows PowerShell engineer.",
    "tools": [{"name": "read_file", "description": "Read a file",
               "input_schema": {"type": "object",
                 "properties": {"path": {"type": "string"}}, "required": ["path"]}}],
    "messages": [{"role": "user", "content": content}]
}).encode()

print(f"payload ~{len(body)//1024}KB, timeout={timeout}s, tries={tries}")
for i in range(tries):
    t0 = time.time()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
            print(f"try{i+1}: HTTP 200 in {time.time()-t0:.1f}s stop={d.get('stop_reason')}")
    except urllib.error.HTTPError as e:
        print(f"try{i+1}: HTTP {e.code} in {time.time()-t0:.1f}s {e.read()[:120]}")
    except Exception as e:
        print(f"try{i+1}: {type(e).__name__} in {time.time()-t0:.1f}s")
    time.sleep(2)
