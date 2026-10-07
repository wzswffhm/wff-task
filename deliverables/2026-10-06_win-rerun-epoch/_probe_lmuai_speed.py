import json
import time
import urllib.request
import urllib.error

KEY = "sk-391b43374428644458bc9a793af01d064d7a285fa7e9a00d4c92debd9e814321"
BASE = "https://api.lmuai.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

prompt = ("Write a PowerShell function that walks a directory tree, resolves every reparse point, "
          "and emits a CSV audit row per entry. Include full parameter blocks, comment-based help, "
          "and detailed inline comments. Be thorough; produce at least 400 lines of code.")

body = json.dumps({"model": "glm-5.3", "max_tokens": 8000,
                   "messages": [{"role": "user", "content": prompt}]}).encode()
req = urllib.request.Request(BASE + "/v1/messages", data=body, method="POST", headers={
    "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json",
    "User-Agent": UA})
t0 = time.time()
try:
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    dt = time.time() - t0
    usage = d.get("usage", {})
    out_tok = usage.get("output_tokens")
    print(f"HTTP 200 in {dt:.1f}s | stop={d.get('stop_reason')} | output_tokens={out_tok} "
          f"| speed={(out_tok/dt if out_tok else 0):.1f} tok/s")
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", "replace")[:200])
except Exception as e:
    print(type(e).__name__, e, f"(after {time.time()-t0:.1f}s)")
