# -*- coding: utf-8 -*-
"""从飞书 Base 记录历史里解析各题包交付附件的上传时间与该记录的状态变更时间。"""
from __future__ import annotations

import datetime
import json
import pathlib

HIST = pathlib.Path(__file__).resolve().parent / "history"
TZ = datetime.timezone(datetime.timedelta(hours=8))
NAMES = {
    "reczz28KwEOO3xHy": "wsparse-215",
    "reczz28KQU8reW2k": "wvas-216",
    "reczz28MRVnWkD2v": "wspawn-218",
    "reczz28N2IGu9XmA": "wcancel-219",
    "reczz28NUOrl6Foj": "wciocp-220",
}


def ts(value: int) -> str:
    return datetime.datetime.fromtimestamp(value, TZ).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    summary = {}
    for rid, label in NAMES.items():
        raw = json.loads((HIST / f"{rid}.json").read_text(encoding="utf-8-sig"))
        items = raw["data"]["items"]
        print("=" * 78)
        print(f"{label}  record={rid}  历史条目 {len(items)}")
        uploads = []
        for it in sorted(items, key=lambda x: x["create_time"]):
            for fc in it.get("field_changes") or []:
                field = fc.get("field_name")
                if field == "作业压缩包":
                    after = fc.get("after")
                    if isinstance(after, list):
                        desc = [(a.get("name"), a.get("size"), a.get("file_token")) for a in after]
                    else:
                        desc = after
                    print(f"   [附件] {ts(it['create_time'])}  rev={it.get('rev')}  "
                          f"操作人={it.get('operator')}  -> {desc}")
                    uploads.append((it["create_time"], desc))
                elif field == "状态":
                    print(f"   [状态] {ts(it['create_time'])}  rev={it.get('rev')}  "
                          f"{fc.get('before')} -> {fc.get('after')}")
        summary[label] = {
            "record_id": rid,
            "attachment_uploads": [
                {"time": ts(t), "files": [{"name": n, "size": s, "file_token": ft}
                                          for n, s, ft in d] if isinstance(d, list) else d}
                for t, d in uploads
            ],
            "history_items": len(items),
        }
    out = pathlib.Path(__file__).resolve().parent / "feishu-upload-times.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
