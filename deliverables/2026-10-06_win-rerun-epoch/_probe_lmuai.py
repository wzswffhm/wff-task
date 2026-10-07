import json
import urllib.request
import urllib.error

KEY = "sk-391b43374428644458bc9a793af01d064d7a285fa7e9a00d4c92debd9e814321"
BASE = "https://api.lmuai.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def call(path, body, headers, tag, timeout=60):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers=headers)
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            txt = ""
            if isinstance(d.get("content"), list) and d["content"]:
                txt = str(d["content"][0].get("text"))[:60]
            print(f"{tag} -> HTTP {r.status} stop={d.get('stop_reason')} text={txt!r}")
            return True
    except urllib.error.HTTPError as e:
        print(f"{tag} -> HTTP {e.code} {e.read().decode('utf-8','replace')[:220]}")
    except Exception as e:
        print(f"{tag} -> {type(e).__name__}: {e}")
    return False


# 1) model listing (OpenAI style)
try:
    req = urllib.request.Request(BASE + "/v1/models", headers={"Authorization": "Bearer " + KEY, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
        ids = [m.get("id") for m in d.get("data", [])]
        print("MODELS:", [i for i in ids if any(k in str(i).lower() for k in ("glm", "kimi", "qwen", "claude"))][:40] or ids[:40])
except urllib.error.HTTPError as e:
    print("MODELS -> HTTP", e.code, e.read().decode("utf-8", "replace")[:200])
except Exception as e:
    print("MODELS ->", type(e).__name__, e)

# 2) anthropic-shape probes with different auth + model ids
for auth_name, headers in [
    ("x-api-key", {"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}),
    ("bearer", {"Authorization": "Bearer " + KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}),
]:
    for model in ["glm-5.3", "glm-4.6"]:
        call("/v1/messages", {"model": model, "max_tokens": 32,
                              "messages": [{"role": "user", "content": "Reply exactly: PONG"}]},
             headers, f"messages/{auth_name}/{model}")
