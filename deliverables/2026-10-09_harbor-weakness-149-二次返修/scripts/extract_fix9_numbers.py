# -*- coding: utf-8 -*-
"""提取 fix9 修复后的压力/反向压力数值，供更新飞书考点信息。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
NEW = json.loads((pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                               r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\out1\_results.json')
                  ).read_text(encoding='utf-8'))
OLD = json.loads((pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                               r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\baseline_fix8\_results.json')
                  ).read_text(encoding='utf-8'))

S = ['S1', 'S2', 'S3', 'S4']


def get(d, plan, sc, tag):
    return d['stress'][f'{plan}|{sc}|{tag}']['total']


print('=== 方案A 沿用冲击 S1-S4 ===')
for sc in S:
    print(f'  {sc}: {get(OLD,"方案A",sc,"committee")*100:.4f}% -> {get(NEW,"方案A",sc,"committee")*100:.4f}%')
print('=== 推荐方案 沿用冲击 S1-S4 ===')
for sc in S:
    print(f'  {sc}: {get(OLD,"推荐方案",sc,"committee")*100:.4f}% -> {get(NEW,"推荐方案",sc,"committee")*100:.4f}%')
print('=== 推荐方案 历史校准 S1-S4 ===')
for sc in S:
    print(f'  {sc}: {get(OLD,"推荐方案",sc,"historical")*100:.4f}% -> {get(NEW,"推荐方案",sc,"historical")*100:.4f}%')
print('=== 方案A 历史校准 S1-S4 ===')
for sc in S:
    print(f'  {sc}: {get(OLD,"方案A",sc,"historical")*100:.4f}% -> {get(NEW,"方案A",sc,"historical")*100:.4f}%')

print('\n=== 各方案最大压力损失 ===')
for p in ['方案A', '方案B', '方案C', '推荐方案']:
    o = OLD['max_stress'][p][0] * 100
    n = NEW['max_stress'][p][0] * 100
    print(f'  {p}: {o:.4f}% -> {n:.4f}%  (旧超限 {abs(o)-8:.3f}pp / 新 {abs(n)-8:.3f}pp)')
o = OLD['max_stress_baseline']['当前持仓'][0] * 100
n = NEW['max_stress_baseline']['当前持仓'][0] * 100
print(f'  当前持仓: {o:.4f}% -> {n:.4f}%')

print('\n=== 反向压力/马氏 ===')
for k in ['reverse_stress', 'md_committee', 'md_historical']:
    print(f'  {k}: old={json.dumps(OLD.get(k), ensure_ascii=False)[:120]}')
    print(f'  {k}: new={json.dumps(NEW.get(k), ensure_ascii=False)[:120]}')

print('\n=== 推荐方案 S4 裕度/放大倍数 ===')
loss = NEW['max_stress']['推荐方案'][0]
print(f'  损失 {loss*100:.4f}%  距 8% 裕度 {(0.08+loss)*100:.4f}pp  放大 {(0.08/abs(loss)):.2f} 倍')
loss_o = OLD['max_stress']['推荐方案'][0]
print(f'  [旧] 损失 {loss_o*100:.4f}%  裕度 {(0.08+loss_o)*100:.4f}pp  放大 {(0.08/abs(loss_o)):.2f} 倍')

print('\n=== 九项约束结果（应不变）===')
for p in ['方案A', '方案B', '方案C', '推荐方案']:
    print(f'  {p}: {NEW["checks"][p]}')
