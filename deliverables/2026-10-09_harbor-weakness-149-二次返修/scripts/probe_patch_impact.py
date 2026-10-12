# -*- coding: utf-8 -*-
"""改一处常量->跑->提取数值 的快速迭代探针。"""
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

R = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
SRC = R / 'solution' / 'golden_output' / 'FIN3-WKN-149_reproduce.py'
PY = r'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
INP = R / 'environment' / 'input_files'
TMP = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\probe')
TXT = TMP / 'FIN3-WKN-149_风险委员会决策备忘录.md'

PATCHES = {
    'BP': [("/ 10000.0 for t in d if t in w_dur)", "/ 100.0 for t in d if t in w_dur)")],
    'SPX': [("""((1 + h.get('SPX', 0)) / (1 + h.get('USD_CASH', 0)) - 1)
                              if h.get('SPX') is not None else 0""",
             "h.get('SPX', 0) / (1 + h.get('USD_CASH', 0)) if h.get('SPX') is not None else 0")],
    'EQ': [("""(w['EQ_000300'] * sh['EQ_000300'] + w['EQ_000905'] * sh['EQ_000905']
                                + w['EQ_399006'] * sh['EQ_399006'])""",
            "(w['EQ_000300'] + w['EQ_000905'] + w['EQ_399006']) * sh['EQ_000300']")],
}

KEY = re.compile(r'(最大压力损失|最大压力损失表|推荐方案|方案A|方案B|方案C|当前持仓)'
                 r'.{0,40}?(-?\d+\.?\d*%)', re.S)


def run(tag, patches, outdir):
    orig = SRC.read_text(encoding='utf-8')
    t = orig
    for a, b in patches:
        assert a in t, f'patch 未命中: {a[:60]}'
        t = t.replace(a, b)
    TMP.mkdir(parents=True, exist_ok=True)
    probe = TMP / f'probe_{tag}.py'
    probe.write_text(t, encoding='utf-8')
    p = subprocess.run([PY, str(probe), str(INP), str(outdir)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = p.stdout or ''
    m = re.search(r'--- 检查 ---\n(.*?)(?:\n\s*\n|--- )', out, re.S)
    checks = m.group(1) if m else '未捕获'
    print(f'=== {tag}  rc={p.returncode} ===')
    print(checks.strip())
    if TXT.exists():
        txt = TXT.read_text(encoding='utf-8')
        for ln in txt.splitlines():
            if any(k in ln for k in ['最大压力损失', '缓冲', '超限', '1.72', '0.0172', '马氏距离']):
                if '%' in ln or '马氏' in ln:
                    print('  备忘录:', ln.strip()[:200])
    print()
    return p.returncode


# 1) 仅关闭修正项（三个 patch 都反向 = 旧代码）
run('none', [p for v in PATCHES.values() for p in v], TMP / 'none')
# 2) 单项关闭
for k in PATCHES:
    run(f'off_{k}', PATCHES[k], TMP / f'off_{k}')
