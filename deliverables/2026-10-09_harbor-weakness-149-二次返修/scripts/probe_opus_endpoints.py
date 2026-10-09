#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 claude-opus-4-8 各候选端点的当前可用性。"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

ENV = pathlib.Path('/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/'
                   '2026-10-04_outside-harbor-win/runner/.env.local')


def load_env(p):
    out = {}
    for ln in p.read_text(encoding='utf-8-sig', errors='ignore').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


env = load_env(ENV)
key = env.get('OPUS_API_KEY') or ''
print(f'OPUS_API_KEY len={len(key)} prefix={key[:12]}...')
print()

BASES = [
    'https://4router.net',
    'https://api.ebondai.com',
]
for base in BASES:
    url = base + '/v1/messages'
    body = json.dumps({'model': 'claude-opus-4-8', 'max_tokens': 16,
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
            print(f'{base}: OK  model={d.get("model")}')
    except urllib.error.HTTPError as e:
        print(f'{base}: HTTP {e.code}  {e.read().decode()[:260]}'.replace('\n', ' '))
    except Exception as e:  # noqa: BLE001
        print(f'{base}: ERR {type(e).__name__} {str(e)[:160]}')
