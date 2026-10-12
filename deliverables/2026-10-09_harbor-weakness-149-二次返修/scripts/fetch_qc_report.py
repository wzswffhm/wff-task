# -*- coding: utf-8 -*-
"""取 FIN3-WKN-149 记录上的「质检报告」附件并下载到本地。"""
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
OUT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\feishu_fields')
OUT.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args):
    p = subprocess.run([LARK] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json")
dd = json.loads(out)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]

print("=== 记录当前关键字段 ===")
for k in ["序号", "题目难度", "状态", "题目附件信息", "标准答案附件信息", "交付物", "质检报告"]:
    if k in idx:
        v = row[idx[k]]
        if isinstance(v, list) and v and isinstance(v[0], dict):
            v = ' | '.join(f'{a.get("name")}({a.get("size")}B,token={a.get("file_token")})' for a in v)
        print(f'  {k:12s}: {str(v)[:200]}')

atts = row[idx["质检报告"]]
atts = atts if isinstance(atts, list) else []
print(f'\n=== 质检报告附件 ({len(atts)}) ===')
for a in atts:
    name = a.get("name")
    tok = a.get("file_token")
    dst = OUT / name
    rc, out, err = lark("base", "+record-download-attachment", "--base-token", BT,
                        "--table-id", TB, "--record-id", REC, "--file-token", tok,
                        "--output", str(dst), "--as", "user", "--format", "json")
    print(f'  下载 {name} ({a.get("size")}B) rc={rc} -> {dst}  exists={dst.exists()}')
    if dst.exists():
        print(f'  实际大小 {dst.stat().st_size:,} B')
