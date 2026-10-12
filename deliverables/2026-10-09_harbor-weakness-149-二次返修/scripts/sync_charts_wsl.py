# -*- coding: utf-8 -*-
"""补齐 fix9 遗漏同步的 5 张金标 PNG 到 WSL 任务目录（solution/golden_output + tests/__golden_output），
并校验 7 件套逐字节一致。"""
import hashlib
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
WIN = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
WSL = pathlib.Path(r'\\wsl.localhost\Ubuntu\home\wff\harbor-tasks-fix8\FIN3-WKN-149')

CH = 'FIN3-WKN-149_charts'
SEVEN = ['FIN3-WKN-149_reproduce.py', 'FIN3-WKN-149_风险委员会决策备忘录.md'] + \
        [f'{CH}/FIN3-WKN-149_chart0{i}_' + n for i, n in enumerate(
            ['数据覆盖与缺口.png', '历史风险总览.png', '情景识别与校准.png',
             '方案决策与执行.png', '监测指标触发状态.png'], start=1)]
DIRS = ['solution/golden_output', 'tests/__golden_output']


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


print('=== 同步（含此前遗漏的 5 张 PNG）===')
allok = True
for d in DIRS:
    print(f'--- {d}')
    for rel in SEVEN:
        src, dst = WIN / d / rel, WSL / d / rel
        before = sha(dst) if dst.exists() else 'MISSING'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        same = sha(src) == sha(dst)
        allok &= same
        mark = 'OK ' if same else 'FAIL'
        chg = '' if before == sha(dst) else f'  ({before} -> {sha(dst)})'
        print(f'  {mark} {rel.split("/")[-1][:40]:42s} {sha(dst)}{chg}')

print(f'\n=== 结果: {"全部一致" if allok else "存在不一致"} ===')
# 再验一次 oracle 运行源
src_png = sorted((WIN / 'solution/golden_output' / CH).glob('*.png'))
print('\n=== WSL solution/golden_output 图（oracle 运行源）===')
for f in sorted((WSL / 'solution/golden_output' / CH).glob('*.png')):
    print(f'  {sha(f)}  {f.stat().st_size:>7}  {f.name}')
sys.exit(0 if allok else 1)
