# -*- coding: utf-8 -*-
"""writeback_215_images.py —— 把已上传的两张截图写进飞书 215 记录。

作业压缩包（52 MB）经实测超出飞书所有 API 通道上限（与 216 当时的结论一致），
需在飞书界面手动拖入；本脚本只负责两个截图字段，并在回读时报告压缩包单元格现状。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
REC = "reczz28KwEOO3xHy"          # 215

IMG_DIR = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
                       r"\_qc_runs\repair-215-216-20261016\feishu-215\images")
WORK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
                    r"\_qc_runs\repair-215-216-20261016\feishu-215")

# 本轮已成功上传（upload_all）得到的 token
PNG = {
    "oracle/nop截图": "GZ7rbwpa3oSNq6xUwXqcEAS8nlf",
    "分数截图":       "J8e2bJp9Io36FKxptmHcI7rLnng",
}
SIZES = {
    "oracle/nop截图": (1560, 3090),
    "分数截图":       (1560, 690),
}


def lark() -> str:
    for cand in (r"C:\nvm4w\nodejs\lark-cli.cmd",):
        if pathlib.Path(cand).exists():
            return cand
    raise SystemExit("找不到 lark-cli.cmd")


CLI = lark()


def run(args, cwd):
    proc = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", shell=True)
    raw = (proc.stdout or "") + (proc.stderr or "")
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j <= i:
        raise SystemExit("lark-cli 未返回 JSON:\n" + raw[:1500])
    doc = json.loads(raw[i:j + 1])
    if doc.get("ok") is False:
        raise SystemExit("lark-cli 报错: " + json.dumps(doc.get("error"), ensure_ascii=False))
    return doc


# 先读当前记录，保留作业压缩包单元格不动
print("[0] 读取当前记录 ...")
g = run([CLI, "base", "+record-get", "--as", "user", "--base-token", BASE,
         "--table-id", TABLE, "--record-id", REC, "--format", "json"], cwd=WORK)
fields = list(g["data"]["fields"])
rows = g["data"]["data"]
row = rows[0] if rows else []
cur = {name: (row[i] if i < len(row) else None) for i, name in enumerate(fields)}
cur_zip = [c for c in (cur.get("作业压缩包") or []) if c]
print("    作业压缩包 现有 %d 件: %s"
      % (len(cur_zip), ", ".join("%s(%s)" % (c.get("name"), c.get("size")) for c in cur_zip) or "空"))

cells = {}
for name, token in PNG.items():
    w, h = SIZES[name]
    cells[name] = [{"file_token": token, "image_width": w, "image_height": h}]
# 整体赋值会清空未列出的字段，因此把压缩包现状原样带回
if cur_zip:
    cells["作业压缩包"] = [{"file_token": c.get("file_token")} for c in cur_zip]

body = WORK / ".record.json"
body.write_text(json.dumps({"fields": cells}, ensure_ascii=False), encoding="utf-8")
print("[1] PUT 写入截图字段 ...")
try:
    res = run([CLI, "api", "PUT",
               "/open-apis/bitable/v1/apps/%s/tables/%s/records/%s" % (BASE, TABLE, REC),
               "--as", "user", "--data", "@.record.json", "--format", "json"], cwd=WORK)
    print("    code =", res.get("code"))
finally:
    body.unlink(missing_ok=True)

print("[2] 回读验证 ...")
g2 = run([CLI, "base", "+record-get", "--as", "user", "--base-token", BASE,
          "--table-id", TABLE, "--record-id", REC, "--format", "json"], cwd=WORK)
f2 = list(g2["data"]["fields"])
r2 = (g2["data"]["data"] or [[]])[0]
idx = {name: (r2[i] if i < len(r2) else None) for i, name in enumerate(f2)}

ok = True
for name in PNG:
    cell = [c for c in (idx.get(name) or []) if c]
    want = IMG_DIR.name and {
        "oracle/nop截图": "oracle_nop_controls.png",
        "分数截图": "score_summary.png",
    }[name]
    exact = [c for c in cell if c.get("name") == want]
    state = "匹配且唯一" if (len(exact) == 1 and len(cell) == 1) else "**异常**"
    print("    %-14s %s（格内 %d 件: %s）"
          % (name, state, len(cell),
             ", ".join("%s(%s)" % (c.get("name"), c.get("size")) for c in cell)))
    if state != "匹配且唯一":
        ok = False

zip_cell = [c for c in (idx.get("作业压缩包") or []) if c]
print("    作业压缩包    格内 %d 件: %s"
      % (len(zip_cell), ", ".join("%s(%s)" % (c.get("name"), c.get("size")) for c in zip_cell) or "空"))

print("\n结论：截图 %s；作业压缩包需人工拖入" % ("已写入" if ok else "**写入异常**"))
sys.exit(0 if ok else 1)
