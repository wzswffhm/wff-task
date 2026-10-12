# -*- coding: utf-8 -*-
"""fix9 终态复核：飞书记录全字段 + 本地包 + 关键一致性。"""
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
    return str(v)[:150]


print('=== 飞书记录终态 ===')
for k in ['序号', '题目难度', '状态', '类型', '题目附件信息', '标准答案附件信息', '交付物', '质检报告']:
    if k in idx:
        print(f'  {k:12s}: {show(row[idx[k]])}')

qd = row[idx['考点信息（rubrics）']]
print(f'\n=== 考点信息一致性（{len(qd)} 字）===')
for bad in ['9.902', '7.030', '5.045', '8.916', '6.650', '15.19', '50.77', '1.59 倍', '20 个下限']:
    c = qd.count(bad)
    print(f'  旧值「{bad}」残留: {c}  {"OK" if c == 0 else "⚠"}')
for good in ['10.157', '7.456', '5.565', '9.257', '6.957', '18.38', '52.08', '1.44 倍', '2.435']:
    print(f'  新值「{good}」: {qd.count(good)}')

print('\n=== 本地包 ===')
for f in [H / 'FIN3-WKN-149_task.zip', H / 'FIN3-WKN-149_answer.zip',
          H / 'work_fin-b01_20261011_fix9-149.zip']:
    print(f'  {f.name}: {f.stat().st_size:,} B  exists={f.is_file()}')

print('\n=== 批次包内金标一致性抽查 ===')
bz = zipfile.ZipFile(H / 'work_fin-b01_20261011_fix9-149.zip')
rp = bz.read('work_fin-b01_20261011_fix9-149/FIN3-WKN-149/solution/golden_output/'
             'FIN3-WKN-149_reproduce.py').decode('utf-8')
print(f'  金标脚本含 /10000.0: {"/ 10000.0" in rp}')
print(f'  金标脚本含 (1+SPX)/(1+USD)-1: {"((1 + h.get(\'SPX\', 0)) / (1 + h.get(\'USD_CASH\', 0)) - 1)" in rp}')
print(f'  金标脚本境内权益逐项加权: {"w[\'EQ_000905\'] * sh[\'EQ_000905\']" in rp}')
sm = json.loads(bz.read('work_fin-b01_20261011_fix9-149/FIN3-WKN-149/'
                        '跑分产物与轨迹/summary.json').decode('utf-8'))
print(f'  summary: batch={sm["batch"]}  mean={sm["model_mean"]:.6f}  gate_pass={sm["gate_pass"]}')
for m, v in sm['executors'].items():
    print(f'    {m:20s} reward={v["reward"]}  counted={v["criteria_counted"]}  err={v["verifier_error"]}')
