#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 fix8 四执行体轨迹中的凭据与不可见空白，供归档前脱敏判定。"""
import pathlib
import re
import sys

ROOT = pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8')
PATTERNS = {
    'sk-token': re.compile(r'sk-[A-Za-z0-9._\-]{12,}'),
    'anthropic-key': re.compile(r'sk-ant-[A-Za-z0-9._\-]{10,}'),
    'bearer': re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]{20,}'),
    'ideographic-space': re.compile('\u3000'),
    'nbsp': re.compile('\u00a0'),
}
TRIAL_DIRS = {
    'oracle': 'trials-oracle/FIN3-WKN-149__FKYpS8d',
    'qwen': 'trials-qwen/FIN3-WKN-149__uqNx7ti',
    'gpt': 'trials-gpt/FIN3-WKN-149__qsFcMtD',
    'opus': 'trials-opus/FIN3-WKN-149__6AB4Ng8',
}

print('=== 轨迹文件扫描 ===')
for name, rel in TRIAL_DIRS.items():
    adir = ROOT / rel / 'agent'
    if not adir.is_dir():
        print(f'{name:8s} MISSING {adir}')
        continue
    for f in sorted(adir.rglob('*')):
        if not f.is_file():
            continue
        try:
            t = f.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:  # noqa: BLE001
            print(f'  {name} {f.name}: read err {e}')
            continue
        hits = {k: len(p.findall(t)) for k, p in PATTERNS.items()}
        hits = {k: v for k, v in hits.items() if v}
        print(f'  {name:6s} {str(f.relative_to(ROOT)):60s} {f.stat().st_size:>9} B  {hits}')
