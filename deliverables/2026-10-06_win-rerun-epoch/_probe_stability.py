import json, sys, time, urllib.request, urllib.error

KEY = "sk-ff432bac0d50207c49ea61f7df586d5c003332dea2e4bb87826189e28db5ce4c"
URL = "https://api.ebondai.com/v1/messages"
PROXY = sys.argv[1] if len(sys.argv) > 1 else ""  # "" = direct, e.g. http://127.0.0.1:7897
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8

handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY} if PROXY else {})
opener = urllib.request.build_opener(handler)

ok = fail = 0
codes = []
for i in range(N):
    body = json.dumps({"model": "claude-opus-5", "max_tokens": 16,
                       "messages": [{"role": "user", "content": "Reply: PONG"}]}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with opener.open(req, timeout=30) as r:
            codes.append(r.status); ok += 1
    except urllib.error.HTTPError as e:
        codes.append(e.code); fail += 1
    except Exception as e:
        codes.append(type(e).__name__[:12]); fail += 1
    time.sleep(2)

print(f"proxy={PROXY or 'DIRECT'} ok={ok} fail={fail} codes={codes}")
