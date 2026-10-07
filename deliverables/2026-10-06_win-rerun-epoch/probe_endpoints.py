"""Probe every configured model endpoint for reachability and identity.

Reads credentials in-process and never prints them: only the host, the auth
scheme, the HTTP status and a short redacted excerpt of the response body are
written to stdout.  A 200 that answers the probe prompt correctly means the
endpoint is *usable*; anything else means a rerun would be wasted work.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RUNNER = Path(r"C:/Users/Administrator/Desktop/wff-task/deliverables/2026-10-04_outside-harbor-win/runner")
ENV_LOCAL = RUNNER / ".env.local"
HARBOR_ENV = Path(r"C:/Users/Administrator/.workbuddy/harbor-windows.env")

PROMPT = "Reply with exactly one word: PONG"


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def redact(text: str) -> str:
    """Keep the shape of an error but never echo a credential."""
    text = text.replace("\n", " ")[:220]
    for token in ("sk-", "ark-", "Bearer ", "x-api-key"):
        if token in text:
            head = text.split(token)[0]
            return head + "<REDACTED>"
    return text


def probe(label: str, base: str, key: str, model: str, auth: str,
          extra: dict[str, str] | None = None, timeout: int = 45) -> dict:
    if not (base and key and model):
        return {"label": label, "status": "MISSING_CONFIG", "detail": "base/key/model absent"}

    url = base.rstrip("/") + "/v1/messages"
    body = {
        "model": model,
        "max_tokens": 16,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    scheme = "bearer" if "bearer" in (auth or "").lower() else "x-api-key"
    if scheme == "bearer":
        headers["authorization"] = "Bearer " + key
    else:
        headers["x-api-key"] = key
    if extra:
        for k, v in extra.items():
            if k and v:
                headers[k] = v

    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8", "replace")
            code = resp.status
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        code = exc.code
    except Exception as exc:  # noqa: BLE001 - probe must never raise
        return {
            "label": label,
            "host": base.split("/")[2] if "//" in base else base,
            "model": model,
            "scheme": scheme,
            "status": "TRANSPORT_ERROR",
            "detail": redact(f"{type(exc).__name__}: {exc}"),
            "elapsed": round(time.time() - started, 2),
        }

    elapsed = round(time.time() - started, 2)
    text = payload
    try:
        parsed = json.loads(payload)
        blocks = parsed.get("content") or []
        text = " ".join(b.get("text", "") for b in blocks if isinstance(b, dict)) or json.dumps(parsed)[:200]
        stop = parsed.get("stop_reason")
    except Exception:  # noqa: BLE001
        stop = None

    return {
        "label": label,
        "host": base.split("/")[2] if "//" in base else base,
        "model": model,
        "scheme": scheme,
        "http": code,
        "reply": redact(text),
        "stop_reason": stop,
        "usable": code == 200 and "PONG" in text.upper(),
        "elapsed": elapsed,
    }


def main() -> int:
    env = load_env(ENV_LOCAL)
    harbor = load_env(HARBOR_ENV)

    results = []
    for alias in ("OPUS", "QWEN", "GLM", "KIMI"):
        extra = {}
        raw_extra = env.get(f"{alias}_EXTRA_JSON")
        if raw_extra:
            try:
                extra = json.loads(raw_extra)
            except Exception:  # noqa: BLE001
                extra = {}
        results.append(probe(
            f"{alias} (runner/.env.local)",
            env.get(f"{alias}_BASE_URL", ""),
            env.get(f"{alias}_API_KEY", ""),
            env.get(f"{alias}_MODEL", ""),
            env.get(f"{alias}_AUTH", ""),
            extra,
        ))

    # Endpoints named by the qualification contract, probed with the keys the
    # environment file carries (may or may not be valid).
    blvr_key = harbor.get("HARBOR_WINDOWS_BLVR_KEY", "")
    if blvr_key:
        results.append(probe("BLVR (contract-specified Opus)", "https://api.blvr.top", blvr_key, "claude-opus-5", "x-api-key"))

    aliyun_key = harbor.get("HARBOR_WINDOWS_ALIYUN_KEY", "")
    if aliyun_key:
        results.append(probe(
            "ALIYUN (endpoints json list)",
            "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic",
            aliyun_key, "qwen3.8-max-0902", "x-api-key",
        ))

    raw_list = harbor.get("HARBOR_WINDOWS_ENDPOINTS_JSON", "")
    if raw_list:
        try:
            parsed = json.loads(raw_list)
            entries = parsed if isinstance(parsed, list) else parsed.get("endpoints", [])
            names = [e.get("name") or e.get("label") or e.get("url") for e in entries if isinstance(e, dict)]
            results.append({"label": "HARBOR_WINDOWS_ENDPOINTS_JSON", "entries": names})
        except Exception as exc:  # noqa: BLE001
            results.append({"label": "HARBOR_WINDOWS_ENDPOINTS_JSON", "detail": redact(str(exc))})

    print(json.dumps(results, ensure_ascii=False, indent=2))
    usable = [r for r in results if r.get("usable")]
    print("\n=== usable endpoints: %d / %d ===" % (len(usable), len([r for r in results if "http" in r or r.get("status")])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
