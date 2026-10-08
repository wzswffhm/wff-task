"""全表扫描：列出所有行摘要，并标注哪些含 FIN3-WKN 编号 / 标注人 wff。"""
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

def cell(row, nm):
    i = idx.get(nm)
    return row[i] if i is not None and i < len(row) else None

print(f"字段={names}")
print(f"总行数={len(rows)}  rev={dd.get('rev')}\n")

fin = {}
for ri, row in enumerate(rows):
    rid = recids[ri] if ri < len(recids) else "?"
    blob = json.dumps(row, ensure_ascii=False)
    for m in re.finditer(r"FIN3-WKN-\d+", blob):
        fin.setdefault(m.group(0), []).append((ri, rid))
    annot = json.dumps(cell(row, "标注人"), ensure_ascii=False)
    status = json.dumps(cell(row, "状态"), ensure_ascii=False)
    seq = cell(row, "序号")
    typ = json.dumps(cell(row, "类型"), ensure_ascii=False)
    sheet = json.dumps(cell(row, "原工作表"), ensure_ascii=False)
    title = str(cell(row, "题目") or "")
    kp = str(cell(row, "考点信息（rubrics）") or "")
    ans = str(cell(row, "参考答案") or "")
    qc = cell(row, "质检报告")
    dl = cell(row, "交付物")
    ta = cell(row, "题目附件信息")
    n_qc = len(qc) if isinstance(qc, list) else (0 if qc is None else 1)
    n_dl = len(dl) if isinstance(dl, list) else (0 if dl is None else 1)
    n_ta = len(ta) if isinstance(ta, list) else (0 if ta is None else 1)
    tag = "★WFF" if "wff" in annot else "    "
    print(f"{tag} r{ri:02d} {rid} seq={seq} 类型={typ} 表={sheet} "
          f"题len={len(title)} 考点len={len(kp)} 答案len={len(ans)} "
          f"附件={n_ta} 交付物={n_dl} 质检={n_qc} 状态={status[:14]}")
    print(f"      题目头: {title[:56]!r}")

print("\n=== 含 FIN3-WKN 编号的行 ===")
for k, v in sorted(fin.items()):
    print(f"  {k}: {v}")
