# -*- coding: utf-8 -*-
"""生成 fix9（本轮返修）run configs：
- oracle: 新 trial（agent 重跑修复后金标，G4 须=1.0）
- 三模型: regrade 模式（复用 fix8 正式 trial 的 agent 产物，只重跑 verifier）
配置源自 fix8 config，trials_dir 指向 fix9 新目录。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
SRC = pathlib.Path(r'C:\Users\Administrator\.wff-creds\fin149_fix8_configs')
DST = pathlib.Path(r'C:\Users\Administrator\.wff-creds\fin149_fix9_configs')
DST.mkdir(exist_ok=True)

# fix9 正式 trial（三模型复用 fix8 的产物）
FIX8_TRIALS = {
    'oracle': 'FIN3-WKN-149__FKYpS8d',   # 仅作参考，oracle 会开新 trial
    'qwen': 'FIN3-WKN-149__uqNx7ti',
    'gpt': 'FIN3-WKN-149__qsFcMtD',
    'opus': 'FIN3-WKN-149__vTPHQTW',
}

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

# 1) oracle start config（trials_dir 改为 fix9 目录）
oc = load(SRC / 'oracle.json')
oc['task']['path'] = '/home/wff/harbor-tasks-fix8/FIN3-WKN-149'
oc['trials_dir'] = '/home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle'
(DST / 'oracle.json').write_text(json.dumps(oc, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[OK] oracle.json -> {DST/"oracle.json"}  (start, 新 trial, trials_dir=fix9)')

# 2) regrade 用的 verifier env（从各 config 提取，供 harbor trial regrade --ve 传参）
verifier_env = load(SRC / 'oracle.json').get('verifier', {}).get('env', {})
(DST / 'verifier_env.json').write_text(
    json.dumps(verifier_env, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[OK] verifier_env.json -> 共 {len(verifier_env)} 键')

# 3) 记录三模型的 source trial 与 agent env（供 regrade 或必要时 start）
meta = {}
for m in ['qwen', 'gpt', 'opus']:
    c = load(SRC / f'{m}.json')
    meta[m] = {
        'source_trial': FIX8_TRIALS[m],
        'source_trials_dir': f'/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-{m}',
        'agent_model': c.get('agent', {}).get('model_name'),
        'verifier_env': c.get('verifier', {}).get('env'),
    }
(DST / 'regrade_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding='utf-8')
print(f'[OK] regrade_meta.json -> 三模型 source trial 记录')
for m, v in meta.items():
    print(f'    {m}: source={v["source_trial"]}  model={v["agent_model"]}')
