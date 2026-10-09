# -*- coding: utf-8 -*-
"""检查飞书文本字段（参考答案 / 考点信息）是否残留旧窗口口径，并落盘全文备查。"""
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
OUTDIR = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                      r'\2026-10-09_harbor-weakness-149-二次返修\feishu_fields')
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

p = subprocess.run([LARK, "base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
dd = json.loads(p.stdout)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]

OUTDIR.mkdir(parents=True, exist_ok=True)
SUSPECT = ['逐日', '全部为负', '均为负', '不少于 20', '不少于20', '20 个下限', '20个下限']

for name in ['参考答案', '考点信息（rubrics）']:
    v = row[idx[name]]
    txt = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    f = OUTDIR / f'{name.replace("（", "_").replace("）", "")}.txt'
    f.write_text(txt, encoding='utf-8')
    print(f'=== {name}  (长度 {len(txt)} 字, 已存 {f.name})')
    hits = [s for s in SUSPECT if s in txt]
    print(f'  旧口径可疑词命中: {hits or "无"}')
    for s in ['累计收益', '累计', '窗口']:
        if s in txt:
            i = txt.find(s)
            print(f'  含「{s}」…{txt[max(0, i - 60):i + 90]}')
            break
    print()

# 完整的备考文本里关于难度/档位的表述
for name in ['参考答案', '考点信息（rubrics）']:
    txt = row[idx[name]] if isinstance(row[idx[name]], str) else ''
    for s in ['A1', 'A2', 'A3', '难度', '档']:
        if s in txt:
            i = txt.find(s)
            print(f'{name} 含「{s}」: ...{txt[max(0, i - 50):i + 70]}...')
