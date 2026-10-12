# -*- coding: utf-8 -*-
"""fix10 文档收尾：以实际 Oracle 试次号与分数回填 §3.1、§9，并核验全文一致性。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
BATCH = H / 'work_fin-b01_20261011_fix10-149'
DOC = BATCH / '交付文档.md'
ARCH = BATCH / 'FIN3-WKN-149' / '跑分产物与轨迹'
TRIAL_NAME = 'FIN3-WKN-149__YbBiCYB'

r = json.loads((ARCH / 'oracle' / 'reward.json').read_text(encoding='utf-8'))
o_r, o_c, o_e = r['reward'], r['criteria_counted'], r['verifier_error']
sm = json.loads((ARCH / 'summary.json').read_text(encoding='utf-8'))
mean = sm['model_mean']

t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'

FIX = [
    # §3.1 reward 行
    ('| `reward` | **1.000000** | **> 0.85** | **PASS** |',
     f'| `reward` | **{o_r:.6f}** | **> 0.85** | **PASS** |'),
    # §3.1 试次说明
    ('> 36 条判据全部纳入判分（判官逐条 individual 会话）。试次：`FIN3-WKN-149__DRcKq7u`（2026-10-11，修复后金标新跑）。',
     f'> 36 条判据全部纳入判分（判官逐条 individual 会话）。试次：`{TRIAL_NAME}`'
     f'（2026-10-11，**fix10 真实同源产物补跑**：Oracle 五图与 `solution/golden_output` 逐字节一致）。'),
    # §9 占位符
    ("""`FIN3-WKN-149__('{"__PLACEHOLDER__"}')`""", f'`{TRIAL_NAME}`'),
    # §9 项3 闭环证据里的试次号措辞
    ('② Oracle 新试次 `FIN3-WKN-149__YbBiCYB`（见 §3.1 实测试次号）；',
     f'② Oracle 新试次 `{TRIAL_NAME}`（fix10），产物**与 `solution/golden_output` 逐字节一致**；'),
]
n_ok = 0
for old, new in FIX:
    c = t.count(old)
    print(f'  {"OK " if c == 1 else "WARN"} {c} 处: {old[:56]}...')
    if c == 1:
        n_ok += 1
    t = t.replace(old, new)
if n_ok != len(FIX):
    # 占位符可能已被首次替换掉，做一次兜底
    t = t.replace("""('{"__PLACEHOLDER__"}')""", f'`{TRIAL_NAME}`')

# §3.2 表头说明补一句「本轮三模型不重跑」
old32 = ('冻结口径：框架 claude-code **2.1.114**，裁判 **qwen3.7-plus**，每模型 1 次，'
         '全程 `--agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode` 禁用 Plan Mode。')
new32 = ('冻结口径：框架 claude-code **2.1.114**，裁判 **qwen3.7-plus**，每模型 1 次，'
         '全程 `--agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode` 禁用 Plan Mode。'
         '**本轮（fix10）三模型 agent 不重跑、亦不重判**（质检报告(3) 明示"现有 agent 作答可保留"、'
         '"不要求无改动判官重复抽样"），故下表分数与试次号沿用 fix9 轮结果。')
c = t.count(old32)
print(f'  {"OK " if c == 1 else "WARN"} §3.2 表头 {c} 处')
t = t.replace(old32, new32, 1)

DOC.write_bytes(t.encode('utf-8'))
print(f'\n[OK] 文档 {len(t.encode("utf-8")):,} B')
print(f'[检查] 残留 PLACEHOLDER: {t.count("PLACEHOLDER")}')
print(f'[检查] YbBiCYB 出现 {t.count(TRIAL_NAME)} 次')
for ln in t.split(NL):
    if ln.startswith('| `reward`') or '试次：' in ln or 'Oracle 新试次' in ln:
        print('  ', ln.strip()[:170])
