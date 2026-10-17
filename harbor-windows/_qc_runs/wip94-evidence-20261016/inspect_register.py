# -*- coding: utf-8 -*-
"""查看 wip94-register 里 VV-24 / VV-25 / VV-35 的判定与证据字段。"""
import json
import pathlib

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables"
                 r"\2026-10-14_wvas216-替换\evidence\manual-review\wip94-register.json")
d = json.loads(P.read_text(encoding="utf-8"))
items = d["items"]
print("total", d["total"], "counts", d["counts"])
print("sample keys:", list(items[0].keys()))
print()
for it in items:
    ident = str(it.get("id") or it.get("code") or "")
    if ident in ("VV-24", "VV-25", "VV-35"):
        print("=" * 70)
        print(json.dumps(it, ensure_ascii=False, indent=1)[:2000])
