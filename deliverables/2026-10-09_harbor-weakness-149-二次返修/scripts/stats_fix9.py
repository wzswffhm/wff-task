# -*- coding: utf-8 -*-
"""从归档后的 reward-details.json 统计四执行体零分判据分布（fix8 同款结构解析）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
ARCH = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                    r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹')
MODELS = ['oracle', 'qwen3.8-max-0902', 'gpt-5.6-sol', 'claude-opus-4-8']


def stats(m):
    d = json.loads((ARCH / m / 'reward-details.json').read_text(encoding='utf-8'))['reward']
    cs = d['criteria']
    zs = [(it['id'], it.get('weight') or 0) for it in cs
          if abs(float(it.get('value') or 0.0)) < 1e-12]
    return d['score'], zs


rows = {}
for m in MODELS:
    sc, zs = stats(m)
    rows[m] = (sc, zs)
    zs_str = ' '.join(f'`{i}`({w:g})' for i, w in zs) if zs else '—（无零分判据）'
    print(f'{m:20s} score={sc:.6f}  零分={len(zs)}  {zs_str}')

# 三模型共同全零
tri = [m for m in MODELS if m != 'oracle']
sets = [set(i for i, _ in rows[m][1]) for m in tri]
common = set.intersection(*sets) if sets else set()
print(f'\n三模型共同全零: {sorted(common)}')
if common:
    wmap = {i: w for i, w in rows[tri[0]][1]}
    print(f'  权重和 = {sum(wmap.get(i, 0) for i in common)}')
    oz = set(i for i, _ in rows['oracle'][1])
    print(f'  其中 oracle 也为 0 的: {sorted(common & oz) or "无（均为金标准可达的真实弱点）"}')

# 写回 summary.json 的 zero 分布（若需）
print('\n（仅统计，未改 summary.json — summary 记录 executors 分数即可）')
