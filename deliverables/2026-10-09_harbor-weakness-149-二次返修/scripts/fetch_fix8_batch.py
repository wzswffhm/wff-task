# -*- coding: utf-8 -*-
"""从飞书「交付物信息」字段下载 fix8 批次包，解出交付文档作 fix9 基线。"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
OUT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\feishu_fields')
EXTRACT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                       r'\2026-10-09_harbor-weakness-149-二次返修\_fix8_extract')
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

atts = row[idx["交付物"]]
atts = atts if isinstance(atts, list) else []
print(f"=== 交付物信息 ({len(atts)}) ===")
for a in atts:
    name, tok = a.get("name"), a.get("file_token")
    print(f'  {name}  {a.get("size")}B  token={tok}')
    if name.endswith("fix8-149.zip"):
        dst = OUT / name
        rc, out, err = lark("base", "+record-download-attachment", "--base-token", BT,
                            "--table-id", TB, "--record-id", REC, "--file-token", tok,
                            "--output", str(dst), "--as", "user", "--format", "json")
        print(f'  下载 rc={rc} -> {dst}  exists={dst.exists()}  '
              f'{dst.stat().st_size if dst.exists() else 0:,} B')
        if dst.exists():
            # 解出交付文档与批次结构
            EXTRACT.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dst) as z:
                names = z.namelist()
                print(f'  zip 条目 {len(names)}，含交付文档='
                      f'{any("交付文档" in n for n in names)}')
                z.extractall(EXTRACT)
            print(f'  解压到 {EXTRACT}')
            for p in EXTRACT.rglob("*"):
                if p.is_file() and ("交付文档" in p.name or p.name == "summary.json"):
                    print(f'    {p.relative_to(EXTRACT)}  {p.stat().st_size:,} B')
