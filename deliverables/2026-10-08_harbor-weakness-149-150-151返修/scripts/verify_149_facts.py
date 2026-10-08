"""Verify FIN3-WKN-149 snapshot facts against the claims in package/Feishu text."""
import csv
import pathlib
from datetime import date

base = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\environment\input_files"
)


def rows(name):
    with open(base / name, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


cal = rows("snapshot_trade_calendar.csv")
sse = [r for r in cal if r["exchange"] == "SSE" and r["is_trading_day"] == "1"]
sse_dates = sorted(r["date"] for r in sse)
print("trade_calendar rows total :", len(cal))
print("SSE trading days total    :", len(sse_dates))
print("calendar range            :", sse_dates[0], "->", sse_dates[-1])

lo, hi = "2018-01-02", "2026-06-09"
win = [d for d in sse_dates if lo <= d <= hi]
print(f"SSE trading days {lo}..{hi}: {len(win)}")
print("  first/last in window    :", win[0], win[-1])

gap = [d for d in sse_dates if "2026-06-09" < d <= "2026-09-15"]
print("SSE trading days 2026-06-10..2026-09-15 (gap claim=69):", len(gap))

for nm in ("snapshot_shibor_seg1.csv", "snapshot_shibor_seg2.csv"):
    r = rows(nm)
    print(f"{nm}: n={len(r)} start={r[0]['date']} end={r[-1]['date']}")
r1, r2 = rows("snapshot_shibor_seg1.csv"), rows("snapshot_shibor_seg2.csv")
print("shibor combined records (claim=2000):", len(r1) + len(r2))
print("shibor combined start   (claim=2018-09-03):", min(r1[0]["date"], r2[0]["date"]))
dr = rows("snapshot_dr007.csv")
print("dr007 records (claim=2000):", len(dr), "start:", dr[0]["date"])

print()
print("--- manifest possible_truncation flags ---")
for r in rows("snapshot_data_manifest.csv"):
    if r["possible_truncation"].strip() or "shibor" in r["file"] or "dr007" in r["file"]:
        print(f"  {r['file']:42s} rec={r['records']:>5s} {r['start']}..{r['end']} trunc={r['possible_truncation']!r}")
