# -*- coding: utf-8 -*-
"""回写后终态复核：读 FIN3-WKN-149 记录的关键字段。"""
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

p = subprocess.run([LARK, "base", "+record-list", "--base-token", BT, "--table-id", TB,
                    "--page-size", "100", "--as", "user", "--format", "json"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
dd = json.loads(p.stdout)["data"]
idx = {n: i for i, n in enumerate(dd["fields"])}
row = dd["data"][dd["record_id_list"].index(REC)]

INTEREST = ["序号", "题目难度", "状态", "类型", "题目", "题目附件信息",
            "标准答案附件信息", "交付物", "质检报告", "参考答案", "考点信息（rubrics）"]


def show(v):
    if isinstance(v, list):
        return ' | '.join(
            f'{a.get("name")}({a.get("size")}B)' if isinstance(a, dict) and 'name' in a
            else str(a)[:60] for a in v)
    return str(v)[:180]


print(f'=== FIN3-WKN-149 记录终态（{REC}）===')
for k in INTEREST:
    if k in idx:
        print(f'  {k:14s}: {show(row[idx[k]])}')

batch = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                     r'\work_fin-b01_20261009_fix8-149.zip')
task = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                    r'\FIN3-WKN-149_task.zip')
ans = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\FIN3-WKN-149_answer.zip')
print('\n=== 本地待传包 vs 飞书附件 ===')
for name, f in [('task', task), ('answer', ans), ('batch', batch)]:
    print(f'  {name}: 本地 {f.stat().st_size:,} B')
