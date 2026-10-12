# -*- coding: utf-8 -*-
"""跑修正后的 reproduce.py 并提取关键数值，对照报告期望值。
基线：旧金标（_backup 里的原版）。
"""
import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

R = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
PY = r'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
INP = R / 'environment' / 'input_files'
OLD = R / 'solution' / 'golden_output' / 'FIN3-WKN-149_reproduce.py'
BK = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_backup_task_root_before_fix8'
                  r'\FIN3-WKN-149\solution\golden_output\FIN3-WKN-149_reproduce.py')

def run(script, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    p = subprocess.run([PY, str(script), str(INP), str(outdir)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    rc = p.returncode
    lines = (p.stdout or '').splitlines()
    tail = [l for l in lines if 'exit' not in l][:0] or lines[-12:]
    return rc, '\n'.join(tail)

def extract(outdir):
    """从生成的备忘录提取压力测试数值"""
    memo = list(outdir.glob('*_风险委员会决策备忘录.md'))
    res = list(outdir.glob('_*.json'))
    out = {}
    if res:
        d = json.loads(res[0].read_text(encoding='utf-8'))
        out['max_stress'] = d.get('max_stress')
        out['max_stress_baseline'] = d.get('max_stress_baseline')
        out['checks'] = d.get('checks')
        out['stress_formal_count'] = d.get('stress_formal_count')
        out['hist_windows'] = {k: {kk: vv for kk, vv in v.items() if kk != 'windows'}
                               for k, v in (d.get('hist_windows') or {}).items()}
        out['reverse'] = {k: v for k, v in (d.get('reverse_stress') or d.get('reverse') or {}).items()}
        out['mahalanobis'] = d.get('mahalanobis') or d.get('reverse_mahalanobis')
    return out, memo[0] if memo else None

print('=== 跑修正后脚本 ===')
rc, log = run(OLD, pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                                r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\out1'))
print(f'  rc={rc}\n  {log}')

n = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                 r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\out1')
res_new, memo_new = extract(n)
print('\n=== 修正后 max_stress ===')
for k, v in (res_new.get('max_stress') or {}).items():
    print(f'  {k}: {v}')
print('\n=== 修正后 max_stress_baseline ===')
for k, v in (res_new.get('max_stress_baseline') or {}).items():
    print(f'  {k}: {v}')
print('\n=== 修正后 checks ===')
for k, v in (res_new.get('checks') or {}).items():
    print(f'  {k}: {v}')
print('\n=== 修正后 hist_windows (calib) ===')
for k, v in (res_new.get('hist_windows') or {}).items():
    print(f'  {k}: {json.dumps(v, ensure_ascii=False, default=str)[:300]}')

print(f'\n=== 备忘录: {memo_new} ===')
if memo_new:
    txt = memo_new.read_text(encoding='utf-8')
    for pat in ['5.045', '5.564', '7.030', '7.455', '9.902', '8.916',
                '1.72', '0.0172', '-0.466', '马氏', '反向']:
        if pat in txt:
            idx = txt.find(pat)
            print(f'  含「{pat}」: ...{txt[max(0,idx-40):idx+60]}...')
