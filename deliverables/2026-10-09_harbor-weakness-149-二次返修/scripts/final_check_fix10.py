# -*- coding: utf-8 -*-
"""fix10 终态复核：飞书记录 + 本地包 + 批次包内同源性与根文档位置。"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
NAME = 'work_fin-b01_20261011_fix10-149'
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

p = subprocess.run([LARK, 'base', '+record-list', '--base-token', BT, '--table-id', TB,
                    '--page-size', '100', '--as', 'user', '--format', 'json'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
dd = json.loads(p.stdout)['data']
idx = {n: i for i, n in enumerate(dd['fields'])}
row = dd['data'][dd['record_id_list'].index(REC)]


def show(v):
    if isinstance(v, list):
        return ' | '.join(
            f'{a.get("name")}({a.get("size")}B)' if isinstance(a, dict) and 'name' in a else str(a)[:40]
            for a in v)
    return str(v)[:120]


print('=== 飞书记录终态 ===')
for k in ['序号', '题目难度', '状态', '题目附件信息', '标准答案附件信息', '交付物', '质检报告']:
    if k in idx:
        print(f'  {k:12s}: {show(row[idx[k]])}')

print('\n=== 本地包 ===')
for f in [H / 'FIN3-WKN-149_task.zip', H / 'FIN3-WKN-149_answer.zip', H / f'{NAME}.zip']:
    print(f'  {f.name}: {f.stat().st_size:,} B')

z = zipfile.ZipFile(H / f'{NAME}.zip')
names = z.namelist()
print('\n=== 批次包结构核验 ===')
print(f'  条目 {len(names)}  顶层 {sorted({n.split("/")[0] for n in names})}')
print(f'  交付文档在批次根: {f"{NAME}/交付文档.md" in names}')
print(f'  题目目录层级正确: {any(n == f"{NAME}/FIN3-WKN-149/task.toml" for n in names)}')


def sh(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()[:16]


print('\n=== 同源性（包内 oracle/output vs solution/golden_output）===')
base = f'{NAME}/FIN3-WKN-149/'
files = ['FIN3-WKN-149_reproduce.py', 'FIN3-WKN-149_风险委员会决策备忘录.md'] + \
        [f'FIN3-WKN-149_charts/FIN3-WKN-149_chart0{i}_' + n for i, n in enumerate(
            ['数据覆盖与缺口.png', '历史风险总览.png', '情景识别与校准.png',
             '方案决策与执行.png', '监测指标触发状态.png'], start=1)]
allok = True
for rel in files:
    a = sh(z.read(base + '跑分产物与轨迹/oracle/output/' + rel))
    b = sh(z.read(base + 'solution/golden_output/' + rel))
    ok = a == b
    allok &= ok
    print(f'  {"OK " if ok else "DIFF"} {rel.split("/")[-1][:38]:40s} {a} == {b}')
print(f'  同源性: {"全部一致 ✅" if allok else "存在差异 ⚠"}')

sm = json.loads(z.read(base + '跑分产物与轨迹/summary.json').decode('utf-8'))
print(f'\n=== summary ===')
print(f'  round={sm["round"]}')
print(f'  mean={sm["model_mean"]:.6f}  gate_pass={sm["gate_pass"]}')
for m, v in sm['executors'].items():
    print(f'    {m:20s} trial={v["trial"]:22s} reward={v["reward"]}')
