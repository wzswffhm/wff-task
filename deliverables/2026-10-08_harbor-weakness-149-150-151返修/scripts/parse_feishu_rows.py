"""精确定位 FIN3-WKN-149/150/151 三行，输出质检报告等关键字段。"""
import json
import pathlib
import re
import sys

src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
    r"C:\Users\Administrator\AppData\Local\Temp\feishu_wff_rows.json")
d = json.loads(src.read_text(encoding="utf-8"))
dd = d["data"]
names = dd.get("fields") or []
rows = dd.get("data") or []
recids = dd.get("record_id_list") or []
idx = {nm: i for i, nm in enumerate(names)}

TARGET = ("FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151")
out = []
for ri, row in enumerate(rows):
    rid = recids[ri] if ri < len(recids) else "?"
    blob = json.dumps(row, ensure_ascii=False)
    hit = [t for t in TARGET if t in blob]
    def cell(nm):
        i = idx.get(nm)
        return row[i] if i is not None and i < len(row) else None
    annot = json.dumps(cell("标注人"), ensure_ascii=False)
    if hit or "wff" in annot:
        out.append((ri, rid, hit, cell, annot))

print(f"总行数={len(rows)}  命中行数={len(out)}\n")
for ri, rid, hit, cell, annot in out:
    print("=" * 95)
    print(f"row_index={ri}  record={rid}  含编号={hit or '（无，按标注人筛出）'}")
    for nm in ("序号", "原工作表", "类型", "题目难度", "状态", "标注人"):
        if nm in idx:
            print(f"  {nm:12s} = {json.dumps(cell(nm), ensure_ascii=False)[:220]}")
    for nm in ("交付物", "质检报告", "题目附件信息", "标准答案附件信息"):
        if nm in idx:
            v = cell(nm)
            if isinstance(v, list):
                brief = [{"name": (x.get("name") if isinstance(x, dict) else x),
                          "size": (x.get("size") if isinstance(x, dict) else None),
                          "token": (x.get("file_token") if isinstance(x, dict) else None)}
                         for x in v]
                print(f"  {nm:12s} = {json.dumps(brief, ensure_ascii=False)}")
            else:
                print(f"  {nm:12s} = {json.dumps(v, ensure_ascii=False)[:220]}")
    title = str(cell("题目") or "")
    print(f"  题目        = len={len(title)}  head={title[:60]!r}")
    for nm, fid in (("考点信息（rubrics）", "fldqj9Zstn"), ("参考答案", "fld2LBu2Ns")):
        v = cell(nm)
        if isinstance(v, str):
            print(f"  {nm}: len={len(v)} head={v[:60]!r}")
