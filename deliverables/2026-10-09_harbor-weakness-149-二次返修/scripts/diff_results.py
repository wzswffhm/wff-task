# -*- coding: utf-8 -*-
"""对比 fix8 提交版基线与修复后金标的所有受影响数值：32条正式+8条基准、马氏距离、反向压力、图3/图4相关。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                    r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2')
OLD = json.loads((BASE / 'baseline_fix8' / '_results.json').read_text(encoding='utf-8'))
NEW = json.loads((BASE / 'out1' / '_results.json').read_text(encoding='utf-8'))

print('=== 顶层键 ===')
print(f'  old: {sorted(OLD.keys())}')
print(f'  new: {sorted(NEW.keys())}')
print()

def diff(d_o, d_n, label, keys=None, tol=1e-6):
    diffs = []
    if isinstance(d_o, dict) and isinstance(d_n, dict):
        for k in sorted(set(d_o) | set(d_n)):
            if keys and k not in keys:
                continue
            a, b = d_o.get(k), d_n.get(k)
            if isinstance(a, dict) and isinstance(b, dict):
                diffs += diff(a, b, f'{label}.{k}', None, tol)
            elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
                if abs(a - b) > tol:
                    diffs.append(f'  {label}.{k}: {a} -> {b}')
            elif a != b:
                diffs.append(f'  {label}.{k}: {str(a)[:80]} -> {str(b)[:80]}')
    return diffs

print('=== stress（32条）差异 ===')
d = diff(OLD.get('stress'), NEW.get('stress'), 'stress')
print(f'  差异数={len(d)}')
for x in d[:20]:
    print(x)
if len(d) > 20:
    print(f'  ...({len(d)-20} more)')

print('\n=== stress_baseline（8条）差异 ===')
d = diff(OLD.get('stress_baseline'), NEW.get('stress_baseline'), 'base')
print(f'  差异数={len(d)}')
for x in d[:20]:
    print(x)

print('\n=== max_stress / checks / hist / mahalanobis / reverse 差异 ===')
for key in ['max_stress', 'max_stress_baseline', 'checks', 'hist_windows',
            'mahalanobis', 'reverse_stress', 'reverse', 'reverse_pressure', 'maha',
            'stress_formal_count', 'stress_baseline_count']:
    if key in OLD or key in NEW:
        d = diff(OLD.get(key), NEW.get(key), key)
        print(f'  [{key}] 差异 {len(d)}')
        for x in d[:12]:
            print(x)

# 找所有含 4 位小数的键（如 mahalanobis/reverse）
print('\n=== 递归找含马氏/reverse 的键值 ===')
def walk(o, p=''):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(s in str(k).lower() for s in ['maha', 'reverse', 'mahalanobis', '马氏', 'd2', 'd_sq']):
                print(f'  {p}{k}: {json.dumps(v, ensure_ascii=False)[:200]}')
            walk(v, f'{p}{k}.')
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            walk(v, f'{p}{i}.')
walk(NEW)
