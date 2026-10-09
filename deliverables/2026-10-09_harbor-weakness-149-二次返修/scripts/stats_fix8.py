# -*- coding: utf-8 -*-
"""统计 fix8 四执行体的零分判据分布（reward-details.json 结构：{"reward": {score, criteria[], ...}}）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                    r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹')
MODELS = ['oracle', 'qwen3.8-max-0902', 'claude-opus-4-8', 'gpt-5.6-sol']

rows = {}
for m in MODELS:
    p = BASE / m / 'reward-details.json'
    d = json.loads(p.read_text(encoding='utf-8'))['reward']
    cs = d['criteria']
    if m == 'oracle':
        print('criteria[0] 键:', list(cs[0].keys()))
        print('criteria[0]:', json.dumps(cs[0], ensure_ascii=False)[:400])
        print()
    zeros = []
    for it in cs:
        v = it.get('value', it.get('score'))
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == 0.0:
            zeros.append((it.get('id') or it.get('criterion_id') or '?', it.get('weight') or 0))
    total_w = sum((it.get('weight') or 0) for it in cs)
    rows[m] = {'score': d['score'], 'zeros': zeros, 'n': len(cs), 'total_w': total_w}
    zs = ' '.join(f'{i}({w:g})' for i, w in zeros)
    print(f'{m:20s} score={d["score"]:.6f}  判据数={len(cs)}  权重和={total_w:g}  零分={len(zeros)}  {zs}')

tri = [m for m in MODELS if m != 'oracle']
if all(rows[m]['zeros'] for m in tri):
    common = set(i for i, _ in rows[tri[0]]['zeros'])
    for m in tri[1:]:
        common &= set(i for i, _ in rows[m]['zeros'])
    wmap = {i: w for i, w in rows[tri[0]]['zeros']}
    print('\n三模型共同全零:', sorted(common), ' 权重和 =', sum(wmap.get(i, 0) for i in common))
    oz = set(i for i, _ in rows['oracle']['zeros'])
    print('其中 oracle 也为 0 的:', sorted(common & oz) or '无（即均为金标准可达的真实弱点）')
