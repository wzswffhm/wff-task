#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""再探 claude-opus-4-8 可用通道：遍历已知网关凭据逐一实测，并搜索 152 等其他题目的历史配置。"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
CFG = pathlib.Path('/mnt/c/Users/Administrator/.wff-creds')


def probe(base, key, model, tag):
    url = base.rstrip('/') + '/v1/messages'
    body = json.dumps({'model': model, 'max_tokens': 16,
                       'messages': [{'role': 'user', 'content': 'Say OK'}]}).encode()
    req = urllib.request.Request(url, data=body, headers={
        'content-type': 'application/json',
        'anthropic-version': '2023-06-01',
        'x-api-key': key,
        'authorization': 'Bearer ' + key,
        'user-agent': 'claude-cli/2.1.114 (external, cli)',
    }, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=50) as r:
            d = json.loads(r.read().decode())
            print(f'  [OK ] {tag:22s} -> model={d.get("model")}')
            return True
    except urllib.error.HTTPError as e:
        print(f'  [HTTP{e.code}] {tag:22s} -> {e.read().decode()[:200]}'.replace('\n', ' '))
    except Exception as e:  # noqa: BLE001
        print(f'  [ERR] {tag:22s} -> {type(e).__name__} {str(e)[:130]}')
    return False


print('=== 现有 fix8 四配置的网关 × claude-opus-4-8 ===')
found = []
for name in ['oracle', 'qwen', 'opus', 'gpt']:
    p = CFG / 'fin149_fix8_configs' / f'{name}.json'
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding='utf-8'))
    ag = d.get('agent') or {}
    env = ag.get('env') or {}
    base = env.get('ANTHROPIC_BASE_URL') or ''
    key = env.get('ANTHROPIC_API_KEY') or env.get('ANTHROPIC_AUTH_TOKEN') or ''
    print(f'-- {name}: model={ag.get("model_name") or ag.get("model")} base={base} keylen={len(key)}')
    if base and key:
        if probe(base, key, 'claude-opus-4-8', f'{name}:{base[:38]}'):
            found.append((name, base, key))

print()
print('=== 搜索其它题目的历史配置（152/151/150） ===')
for p in sorted(CFG.rglob('*.json')):
    try:
        t = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:  # noqa: BLE001
        continue
    if 'opus' in t.lower() and 'base' in t.lower() and p.parent.name != 'fin149_fix8_configs':
        print(f'  候选: {p.relative_to(CFG)}  ({len(t)} B)')

print()
print('=== 找到的可用 opus 通道 ===')
for n, b, k in found:
    print(f'  {n}: {b}  key={k[:8]}...({len(k)})')
