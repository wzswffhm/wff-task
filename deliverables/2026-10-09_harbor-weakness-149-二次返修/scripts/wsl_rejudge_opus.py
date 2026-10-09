#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复用 opus 试次已落盘产物，单独重跑判分（等价 harbor verifier 阶段）。

背景：opus 试次 FIN3-WKN-149__6AB4Ng8 的 agent 阶段在写入全部 7 项交付物后，
因 4router 网关余额耗尽返回 403（预扣费额度失败），被 harbor 归类为 UnknownApiError，
verifier 阶段未执行（reward.json 为 fail-closed 占位）。产物完整，故复用产物重跑判分。
"""
import json
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

CFG = pathlib.Path('/mnt/c/Users/Administrator/.wff-creds/fin149_fix8_configs/oracle.json')
RUNDIR = pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8')
TRIAL = RUNDIR / 'trials-opus' / 'FIN3-WKN-149__6AB4Ng8'
WORK = RUNDIR / 'rejudge-opus'
TASK = pathlib.Path('/home/wff/harbor-tasks-fix8/FIN3-WKN-149')
IMAGE = 'fin3-wkn-149__6ab4ng8__env-main:latest'
NAME = 'fin149-opus-rejudge'

cfg = json.loads(CFG.read_text(encoding='utf-8'))
print('config 顶层键:', list(cfg.keys()))
venv = (cfg.get('verifier') or {}).get('env') or cfg.get('verifier_env') or {}
print('verifier.env 键:', list(venv.keys()))

subprocess.run(['docker', 'rm', '-f', NAME], capture_output=True)
if WORK.exists():
    shutil.rmtree(WORK)
(WORK / 'logs' / 'verifier' / 'graded').mkdir(parents=True)
shutil.copytree(TRIAL / 'artifacts' / 'app' / 'output', WORK / 'app' / 'output')
shutil.copytree(TASK / 'environment' / 'input_files', WORK / 'app' / 'input_files')
print('已备好工作区:', WORK)
for p in sorted((WORK / 'app' / 'output').rglob('*')):
    print('   ', p.relative_to(WORK / 'app'))

envs = []
for k, v in venv.items():
    envs += ['-e', f'{k}={v}']

cmd = ['docker', 'run', '-d', '--name', NAME] + envs + [
    '-v', f'{WORK}/app:/app',
    '-v', f'{TASK}/tests:/tests:ro',
    '-v', f'{WORK}/logs/verifier:/logs/verifier',
    IMAGE,
    'bash', '-c', '(bash /tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1',
]
r = subprocess.run(cmd, capture_output=True, text=True)
print('docker run rc=', r.returncode, r.stdout.strip(), r.stderr.strip()[:300])
