# -*- coding: utf-8 -*-
"""实时读取飞书 FIN3-WKN-149 记录，确认各字段当前值。"""
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"

p = subprocess.run([LARK, 'base', '+record-list', '--base-token', BT, '--table-id', TB,
                    '--page-size', '100', '--as', 'user', '--format', 'json'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
dd = json.loads(p.stdout)['data']
idx = {n: i for i, n in enumerate(dd['fields'])}
row = dd['data'][dd['record_id_list'].index(REC)]

print(f'=== 读取时间: {__import__("datetime").datetime.now():%F %T} ===')
print(f'记录 ID: {REC}\n')
for k in ['序号', '题目难度', '状态', '类型', '题目附件信息', '标准答案附件信息', '交付物', '质检报告']:
    if k not in idx:
        continue
    v = row[idx[k]]
    if isinstance(v, list):
        if v and isinstance(v[0], dict):
            s = ' | '.join(f'{a.get("name")}({a.get("size")}B)' for a in v)
        else:
            s = ' | '.join(str(x) for x in v)
    else:
        s = str(v)[:100]
    print(f'  {k:12s}: {s}')

# 考点信息摘要（只验关键新值是否在位）
qd = row[idx['考点信息（rubrics）']]
print(f'\n  考点信息（rubrics）: {len(qd)} 字')
for good in ['10.157', '5.565', '18.38', '52.08']:
    print(f'    新值 {good}: {"在位" if good in qd else "缺失"}')
for bad in ['9.902', '5.045', '15.19', '50.77', '20 个下限']:
    print(f'    旧值 {bad} 残留: {qd.count(bad)}')
