# -*- coding: utf-8 -*-
"""fix10：用新 Oracle 试次的真实同源产物 + 判分，替换批次包内 oracle 目录；
并校验 oracle 五图与 gold 五图逐字节一致（同源性硬证据）。"""
import hashlib
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
BATCH = H / 'work_fin-b01_20261011_fix10-149'
ARCH = BATCH / 'FIN3-WKN-149' / '跑分产物与轨迹'
GOLD = BATCH / 'FIN3-WKN-149' / 'solution' / 'golden_output'
TRIAL = pathlib.Path(r'\\wsl.localhost\Ubuntu\home\wff\harbor-runs\FIN3-WKN-149-fix10'
                     r'\trials-oracle\FIN3-WKN-149__YbBiCYB')
CH = 'FIN3-WKN-149_charts'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def desens(t: str) -> str:
    import re
    t = re.sub(r'sk-[A-Za-z0-9._\-]{12,}', '<REDACTED_CREDENTIAL>', t)
    t = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._\-]{20,}', r'\1<REDACTED_CREDENTIAL>', t)
    return t.replace('\u3000', ' ').replace('\u00a0', ' ')


rj = TRIAL / 'verifier' / 'reward.json'
em = TRIAL / 'verifier' / 'reward_exit_message.json'
if not rj.is_file() or em.is_file():
    print(f'[ERR] Oracle 判分未完成: reward存在={rj.is_file()} exit_msg存在={em.is_file()}')
    sys.exit(1)
reward = json.loads(rj.read_text(encoding='utf-8'))
if float(reward.get('criteria_counted') or 0) < 1 or float(reward.get('verifier_error') or 0) != 0.0:
    print(f'[ERR] Oracle reward 无效: {reward}')
    sys.exit(1)
print(f'[OK] Oracle reward = {reward}')

out = ARCH / 'oracle'
if out.exists():
    shutil.rmtree(out)
(out / '轨迹').mkdir(parents=True)

# 产物（真实同源）
art = TRIAL / 'artifacts' / 'app' / 'output'
shutil.copytree(art, out / 'output', dirs_exist_ok=True)

# 分数
(out / 'reward.json').write_text(json.dumps(reward, ensure_ascii=False, indent=2), encoding='utf-8')
rd = TRIAL / 'verifier' / 'graded' / 'reward-details.json'
det = None
if rd.is_file():
    shutil.copy2(rd, out / 'reward-details.json')
    det = json.loads(rd.read_text(encoding='utf-8'))

# 轨迹
for f in ['oracle.txt']:
    p = TRIAL / 'agent' / f
    if p.is_file():
        (out / '轨迹' / f).write_text(desens(p.read_text(encoding='utf-8', errors='ignore')),
                                      encoding='utf-8')
tl = TRIAL / 'trial.log'
if tl.is_file():
    (out / '轨迹' / 'trial.log').write_text(desens(tl.read_text(encoding='utf-8', errors='ignore')),
                                            encoding='utf-8')
(out / '轨迹' / '说明.txt').write_text(
    'oracle 试次（fix10 同源产物补跑轮）执行修复后 solution/solve.sh，不产生 claude-code 轨迹；\n'
    '本目录保留 harbor oracle agent 日志（oracle.txt）与试次日志（trial.log）作为运行记录；\n'
    '金标准产物见 ../output/，评分结果见 ../reward.json 与 ../reward-details.json。\n', encoding='utf-8')

# ---- 同源性硬证据：oracle 五图 == gold 五图 ----
print('\n=== 同源性校验（oracle/output vs solution/golden_output）===')
allok = True
for rel in ['FIN3-WKN-149_reproduce.py', 'FIN3-WKN-149_风险委员会决策备忘录.md'] + \
           [f'{CH}/FIN3-WKN-149_chart0{i}_' + n for i, n in enumerate(
               ['数据覆盖与缺口.png', '历史风险总览.png', '情景识别与校准.png',
                '方案决策与执行.png', '监测指标触发状态.png'], start=1)]:
    a, b = out / 'output' / rel, GOLD / rel
    ok = a.is_file() and b.is_file() and sha(a) == sha(b)
    allok &= ok
    print(f'  {"OK " if ok else "DIFF"} {rel.split("/")[-1][:40]:42s} '
          f'{sha(a)[:16] if a.is_file() else "MISS"} == {sha(b)[:16] if b.is_file() else "MISS"}')

# 零分
if det:
    cs = (det.get('reward') or det).get('criteria', [])
    zs = [c['id'] for c in cs if abs(float(c.get('value') or 0)) < 1e-12]
    print(f'\n  判据数={len(cs)}  零分={zs or "空集"}  score={(det.get("reward") or det).get("score")}')

# 更新 summary.json 的 oracle 条目
sj = ARCH / 'summary.json'
d = json.loads(sj.read_text(encoding='utf-8'))
d['round'] = 'fix10 (2026-10-11 质检报告(3)：Oracle 同源产物补跑 + 根交付说明移位)'
d['executors']['oracle'] = {
    'trial': TRIAL.name, 'source': 'fix10 new trial（同源产物补跑）',
    'reward': reward.get('reward'), 'graded_score': reward.get('graded_score'),
    'criteria_counted': reward.get('criteria_counted'),
    'verifier_error': reward.get('verifier_error')}
sj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\n[OK] summary.json oracle -> trial={TRIAL.name} reward={reward.get("reward")}')
print(f'[OK] 同源性: {"全部一致" if allok else "存在差异"}')
sys.exit(0 if allok else 1)
