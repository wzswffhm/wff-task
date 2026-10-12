# -*- coding: utf-8 -*-
"""探针：修复项2是否应为 /1000(而非/10000)，且关闭历史校准(spx/eq)是否复现报告金标旧值。"""
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
R = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
SRC = R / 'solution' / 'golden_output' / 'FIN3-WKN-149_reproduce.py'
PY = r'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
INP = R / 'environment' / 'input_files'
TMP = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\_rerun_bp2\probe2')
TXT = TMP / 'FIN3-WKN-149_风险委员会决策备忘录.md'

ORIG = SRC.read_text(encoding='utf-8')
SPX_NEW = """((1 + h.get('SPX', 0)) / (1 + h.get('USD_CASH', 0)) - 1)
                              if h.get('SPX') is not None else 0"""
SPX_OLD = "h.get('SPX', 0) / (1 + h.get('USD_CASH', 0)) if h.get('SPX') is not None else 0"
EQ_NEW = """(w['EQ_000300'] * sh['EQ_000300'] + w['EQ_000905'] * sh['EQ_000905']
                                + w['EQ_399006'] * sh['EQ_399006'])"""
EQ_OLD = "(w['EQ_000300'] + w['EQ_000905'] + w['EQ_399006']) * sh['EQ_000300']"

VARIANTS = {
    # fix8 基线 + 报告口径期望（A=-9.902%、B=-7.030%）：验证「关闭历史校准+bp/100」
    'v_old_all': [('SPX_NEW', SPX_NEW, SPX_OLD), ('EQ_NEW', EQ_NEW, EQ_OLD)],
    # fix8 基线 + 只关历史校准（bp 保持 /10000 修正）
    'v_nohist': [('SPX_NEW', SPX_NEW, SPX_OLD), ('EQ_NEW', EQ_NEW, EQ_OLD)],
    # 修正项2 试 /1000 + 修正项3/4 保持
    'v_bp1000': [('/10000.0', '/ 1000.0')],
    # 修正项2 /1000 + 关历史校准（最可能复现报告值）
    'v_bp1000_nohist': [('/10000.0', '/ 1000.0'), ('SPX_NEW', SPX_NEW, SPX_OLD),
                        ('EQ_NEW', EQ_NEW, EQ_OLD)],
}


def run(tag, patches):
    t = ORIG
    for name, a, b in patches:
        assert a in t, f'{tag}: patch {name} 未命中'
        t = t.replace(a, b)
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / f'p_{tag}.py'
    p.write_text(t, encoding='utf-8')
    o = TMP / tag
    r = subprocess.run([PY, str(p), str(INP), str(o)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    j = sorted(o.glob('_*.json'))
    out = {'rc': r.returncode}
    if j:
        import json
        d = json.loads(j[0].read_text(encoding='utf-8'))
        ms = d.get('max_stress') or {}
        msb = d.get('max_stress_baseline') or {}
        out.update({k: round(v[0], 6) for k, v in ms.items()})
        out.update({k: round(v[0], 6) for k, v in msb.items()})
    else:
        out['err'] = (r.stderr or '')[-300:]
    print(f'{tag:22s} {out}')
    if TXT.exists() and tag == 'v_old_all':
        txt = TXT.read_text(encoding='utf-8')
        for ln in txt.splitlines():
            if '马氏' in ln or '最可能情景' in ln:
                print('   memo:', ln.strip()[:150])


for tag, patches in VARIANTS.items():
    # 统一 patch 解析（'SPX_NEW' 等名字替换为实际字符串）
    real = []
    for name, a, b in patches:
        if name == 'SPX_NEW':
            a = SPX_NEW
        elif name == 'EQ_NEW':
            a = EQ_NEW
        real.append((name, a, b))
    run(tag, [(n, a, b) for n, a, b in real])

print('\n报告期望: A=-0.099020 B=-0.070300 推荐=-0.050450')
print('报告新值: B=-0.074557 推荐=-0.055648')
