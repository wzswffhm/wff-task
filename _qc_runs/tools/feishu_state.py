"""Summarize the Feishu table state so we can see exactly which row is 217 and
what it is still missing. Keeps long text fields out of the model context.
"""
from __future__ import annotations

import json
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu")

fields_doc = json.loads((D / "fields.json").read_text(encoding="utf-8-sig"))
records_doc = json.loads((D / "records.json").read_text(encoding="utf-8-sig"))

fields = fields_doc["data"]["fields"]
names = [f["name"] for f in fields]
print("fields:")
for f in fields:
    print(f"  {f['id']:<14} {f['name']:<16} type={f['type']}")

data = records_doc["data"]
rows = data.get("data") or []
record_ids = data.get("record_id_list") or []
print(f"\nrecord count: {len(rows)}  record_id_list: {len(record_ids)}")

SUMMARY_FIELDS = {"题目方向", "状态", "标注员", "作业ID", "修改日期", "标注日期", "质检员", "公式校验"}

for idx, row in enumerate(rows):
    rec = record_ids[idx] if idx < len(record_ids) else None
    if isinstance(rec, dict):
        rec = rec.get("record_id")
    print(f"\n--- row {idx}  record_id={rec}")
    for i, name in enumerate(names):
        value = row[i] if i < len(row) else None
        if name in SUMMARY_FIELDS:
            print(f"    {name}: {json.dumps(value, ensure_ascii=False)[:200]}")
        elif isinstance(value, list) and value and isinstance(value[0], dict) and "name" in value[0]:
            files = ", ".join(f"{v.get('name')}({v.get('size')})" for v in value)
            print(f"    {name}: [{files}]")
        elif value is None:
            print(f"    {name}: <empty>")
        else:
            text = json.dumps(value, ensure_ascii=False)
            print(f"    {name}: len={len(text)}  head={text[:60]}")
