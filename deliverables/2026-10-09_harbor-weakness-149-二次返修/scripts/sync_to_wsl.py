# -*- coding: utf-8 -*-
"""把 Windows 侧修复后的文件同步到 WSL 任务目录（harbor-tasks-fix8）。"""
import hashlib
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

WIN = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
WSL = pathlib.Path(r'\\wsl.localhost\Ubuntu\home\wff\harbor-tasks-fix8\FIN3-WKN-149')

FILES = [
    'solution/golden_output/FIN3-WKN-149_reproduce.py',
    'solution/golden_output/FIN3-WKN-149_风险委员会决策备忘录.md',
    'tests/__golden_output/FIN3-WKN-149_reproduce.py',
    'tests/__golden_output/FIN3-WKN-149_风险委员会决策备忘录.md',
    'tests/rubrics.toml',
]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

print(f'WSL 目录可访问: {WSL.is_dir()}')
for rel in FILES:
    src, dst = WIN / rel, WSL / rel
    before = sha(dst) if dst.exists() else 'MISSING'
    shutil.copy2(src, dst)
    after = sha(dst)
    same = sha(src) == after
    print(f'  {"OK" if same else "FAIL"}  {rel}\n'
          f'      win={sha(src)}  wsl_before={before}  wsl_after={after}')

# 验证：WSL 侧关键修复特征
print('\n=== WSL 侧修复特征验证 ===')
r = (WSL / 'solution/golden_output/FIN3-WKN-149_reproduce.py').read_text(encoding='utf-8')
checks = {
    'BP单位 /10000.0': '/ 10000.0 for t in d if t in w_dur' in r,
    'BP旧单位 /100.0 已移除': '/ 100.0 for t in d if t in w_dur' not in r,
    'SPX反算含 (1+x)/(1+y)-1': "(1 + h.get('SPX', 0)) / (1 + h.get('USD_CASH', 0)) - 1" in r,
    '境内权益逐项加权': "(w['EQ_000300'] * sh['EQ_000300'] + w['EQ_000905'] * sh['EQ_000905']" in r,
    'rubrics 含 scoring': 'aggregation' in (WSL / 'tests/rubrics.toml').read_text(encoding='utf-8'),
}
for k, v in checks.items():
    print(f'  {"OK" if v else "MISS"}  {k}: {v}')
sys.exit(0 if all(checks.values()) else 1)
