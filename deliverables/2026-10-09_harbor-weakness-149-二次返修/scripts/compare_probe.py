# -*- coding: utf-8 -*-
"""汇总所有运行变体的 max_stress / max_stress_baseline / 九项约束，对照报告期望值。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                    r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2')

DIRS = {
    'baseline_fix8': BASE / 'baseline_fix8',
    'all_fixed': BASE / 'out1',
    'none(revert-all)': BASE / 'probe' / 'none',
    'off_BP(revert BP only)': BASE / 'probe' / 'off_BP',
    'off_SPX': BASE / 'probe' / 'off_SPX',
    'off_EQ': BASE / 'probe' / 'off_EQ',
}

PLANS = ['方案A', '方案B', '方案C', '推荐方案', '当前持仓']
rows = {}
for tag, d in DIRS.items():
    if not d.is_dir():
        rows[tag] = '目录不存在'
        continue
    js = sorted(p for p in d.glob('*.json') if p.name.startswith('_'))
    if not js:
        rows[tag] = f'无 _*.json: {[p.name for p in d.iterdir()]}'
        continue
    j = json.loads(js[0].read_text(encoding='utf-8'))
    ms, msb = j.get('max_stress') or {}, j.get('max_stress_baseline') or {}
    row = {p: round(ms[p][0], 6) for p in PLANS if p in ms}
    for p, v in msb.items():
        row[p] = round(v[0], 6)
    ck = j.get('checks') or {}
    row['_C8C9'] = {p: (ck.get(p, {}).get('C8'), ck.get(p, {}).get('C9')) for p in PLANS if p in ck}
    row['_nformal'] = j.get('stress_formal_count')
    rows[tag] = row

print('=== max_stress (负=损失) ===')
print(f'{"variant":24s} {"方案A":>12s} {"方案B":>12s} {"方案C":>12s} {"推荐方案":>12s} {"当前持仓":>12s}')
for tag, r in rows.items():
    if isinstance(r, str):
        print(f'{tag:24s} {r}')
        continue
    print(f'{tag:24s} ' + ' '.join(f'{r.get(p, float("nan")):12.6f}' for p in PLANS))

print('\n=== 九项约束 C8(≤8%)/C9(≤7%) ===')
for tag, r in rows.items():
    if isinstance(r, str):
        continue
    print(f'{tag:24s} {r.get("_C8C9")}  formal={r.get("_nformal")}')

print('\n报告期望: 推荐=-0.05564754  方案B=-0.074557  (S4 committee)')
print('报告引用金标旧值: 推荐=-0.050450  方案B=-0.070300')
