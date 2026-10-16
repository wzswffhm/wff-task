"""抓取 wff 五条记录的变更历史，定位「返修原因」字段是谁在什么时候改的。"""
import json
import os
import subprocess

BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "history")
os.makedirs(OUTDIR, exist_ok=True)

RECORDS = {
    "reczz28KwEOO3xHy": "wsparse-215",
    "reczz28KQU8reW2k": "wvas-216",
    "reczz28MRVnWkD2v": "wspawn-218",
    "reczz28N2IGu9XmA": "wcancel-219",
    "reczz28NUOrl6Foj": "wciocp-220",
}


def call(rec, max_version=None):
    cmd = ["cmd", "/c", "lark-cli", "base", "+record-history-list", "--base-token", BASE,
           "--table-id", TABLE, "--record-id", rec, "--as", "user",
           "--page-size", "50", "--format", "json"]
    if max_version is not None:
        cmd += ["--max-version", str(max_version)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = proc.stdout or ""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("no json: %s / %s" % (raw[:200], (proc.stderr or "")[:200]))
    return json.loads(raw[start:end + 1])


def main():
    summary = []
    for rec, name in RECORDS.items():
        items, page, seen = [], 0, set()
        max_version = None
        while True:
            doc = call(rec, max_version)
            data = doc.get("data", {})
            batch = data.get("items") or []
            items.extend(batch)
            page += 1
            if not data.get("has_more") or not batch or page > 20:
                break
            # 下一页以本页最旧的 rev 为界
            revs = [it.get("rev") for it in batch if isinstance(it.get("rev"), int)]
            if not revs:
                break
            nxt = min(revs) - 1
            if nxt in seen:
                break
            seen.add(nxt)
            max_version = nxt

        with open(os.path.join(OUTDIR, rec + ".raw.json"), "w", encoding="utf-8") as fh:
            json.dump({"record_id": rec, "package": name, "pages": page, "items": items},
                      fh, ensure_ascii=False, indent=1)

        reason = []
        for it in items:
            for ch in it.get("field_changes") or []:
                if ch.get("field_name") == "返修原因":
                    reason.append({
                        "rev": it.get("rev"),
                        "time": it.get("create_time"),
                        "operator": it.get("operator"),
                        "activity": it.get("activity_type"),
                        "before_head": (ch.get("before") or "")[:120],
                        "after_head": (ch.get("after") or "")[:200],
                        "after_len": len(ch.get("after") or ""),
                    })
        summary.append({"package": name, "record_id": rec, "total_items": len(items),
                        "reason_changes": reason})

    with open(os.path.join(OUTDIR, "reason-changes.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    for s in summary:
        print("==== %s (%s) 历史条目 %d" % (s["package"], s["record_id"], s["total_items"]))
        for c in s["reason_changes"]:
            print("   rev=%s time=%s operator=%s len=%s" % (
                c["rev"], c["time"], c["operator"], c["after_len"]))
            print("      after: %s" % c["after_head"].replace("\n", " ")[:160])


if __name__ == "__main__":
    main()
