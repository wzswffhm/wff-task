"""对 5 条记录重试抓取历史，直到接口可用或重试耗尽。"""
import json
import subprocess
import time

BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
RECORDS = {
    "reczz28KwEOO3xHy": "wsparse-215",
    "reczz28KQU8reW2k": "wvas-216",
    "reczz28MRVnWkD2v": "wspawn-218",
    "reczz28N2IGu9XmA": "wcancel-219",
    "reczz28NUOrl6Foj": "wciocp-220",
}


def call(rec):
    cmd = ["cmd", "/c", "lark-cli", "base", "+record-history-list", "--base-token", BASE,
           "--table-id", TABLE, "--record-id", rec, "--as", "user", "--page-size", "50",
           "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None, raw[:200]
    try:
        return json.loads(raw[start:end + 1]), None
    except Exception as exc:
        return None, "parse: %r %s" % (exc, raw[start:start + 200])


for attempt in range(1, 6):
    doc, err = call("reczz28KwEOO3xHy")
    if doc and doc.get("ok"):
        data = doc.get("data", {})
        print("attempt %d: OK, items=%d has_more=%s" % (
            attempt, len(data.get("items") or []), data.get("has_more")))
        break
    why = (doc or {}).get("error", {}).get("message") if doc else err
    print("attempt %d: FAIL %s" % (attempt, why))
    time.sleep(15)
else:
    print("接口在 5 次尝试后仍不可用")
