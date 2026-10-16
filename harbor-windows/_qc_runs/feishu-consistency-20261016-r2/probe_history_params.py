"""探测 record_history 接口的参数语义：哪种调用能返回历史条目。"""
import json
import subprocess
import time

BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
REC = "reczz28KwEOO3xHy"


def call(max_version=None, page_size=50):
    cmd = ["cmd", "/c", "lark-cli", "base", "+record-history-list", "--base-token", BASE,
           "--table-id", TABLE, "--record-id", REC, "--as", "user",
           "--page-size", str(page_size), "--format", "json"]
    if max_version is not None:
        cmd += ["--max-version", str(max_version)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return {"error": "no-json", "raw": raw[:120]}
    doc = json.loads(raw[start:end + 1])
    if not doc.get("ok"):
        return {"error": doc.get("error", {}).get("message"), "code": doc.get("error", {}).get("code")}
    data = doc.get("data", {})
    items = data.get("items") or []
    revs = [it.get("rev") for it in items if isinstance(it.get("rev"), int)]
    return {"items": len(items), "has_more": data.get("has_more"),
            "rev_min": min(revs) if revs else None, "rev_max": max(revs) if revs else None}


for mv in (None, 4129, 4128, 4100, 4084, 4078, 4056, 4000):
    print("max_version=%-6s -> %s" % (mv, json.dumps(call(mv), ensure_ascii=False)))
    time.sleep(1.5)
