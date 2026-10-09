#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1) 列出 .env.local 的全部变量名（不打印值）；2) 搜索工作区内所有 opus 网关配置；
3) 用接近真实 agent 负载的请求实测 4router 是否仍可用。"""
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
W = pathlib.Path('/mnt/c/Users/Administrator/Desktop/wff-task')

print('=== 1) .env.local 变量名 ===')
for envp in [W / 'deliverables/2026-10-04_outside-harbor-win/runner/.env.local',
             pathlib.Path('/mnt/c/Users/Administrator/.wff-creds/judge.env')]:
    if not envp.exists():
        print(f'  (缺) {envp}')
        continue
    print(f'-- {envp.name}')
    for ln in envp.read_text(encoding='utf-8-sig', errors='ignore').splitlines():
        ln = ln.strip()
        if ln and not ln.startswith('#') and '=' in ln:
            k, v = ln.split('=', 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            kind = 'URL' if 'http' in v else f'len={len(v)}'
            print(f'   {k:28s} {kind}')

print()
print('=== 2) 工作区内含 opus 网关配置的文件（排除轨迹/产物） ===')
pat = re.compile(r'claude-opus-4-8')
for p in W.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in ('.json', '.local', '.env', '.py', '.toml', '.sh', '.txt', '.md'):
        continue
    if any(x in p.parts for x in ('轨迹', 'output', 'artifacts', 'harbor-runs', '_backup', 'node_modules', '.git')):
        continue
    try:
        t = p.read_text(encoding='utf-8', errors='ignore')
    except Exception:  # noqa: BLE001
        continue
    if pat.search(t) and ('http' in t or 'API_KEY' in t or 'base_url' in t.lower()):
        urls = sorted(set(re.findall(r'https?://[A-Za-z0-9._\-]+', t)))
        print(f'   {p.relative_to(W)}  urls={urls[:4]}')

print()
print('=== 3) 4router 负载实测（模拟真实 agent 请求） ===')
key = None
envp = W / 'deliverables/2026-10-04_outside-harbor-win/runner/.env.local'
for ln in envp.read_text(encoding='utf-8-sig', errors='ignore').splitlines():
    ln = ln.strip()
    if ln.startswith('OPUS_API_KEY='):
        key = ln.split('=', 1)[1].strip().strip('"').strip("'")
if key:
    for label, nchar, mt in [('小请求 16 tok', 60, 16), ('中请求 20k字/2k tok', 20000, 2000), ('大请求 60k字/8k tok', 60000, 8000)]:
        body = json.dumps({'model': 'claude-opus-4-8', 'max_tokens': mt,
                           'messages': [{'role': 'user', 'content': 'A' * nchar + '\nSay OK'}]}).encode()
        req = urllib.request.Request('https://4router.net/v1/messages', data=body, headers={
            'content-type': 'application/json', 'anthropic-version': '2023-06-01',
            'x-api-key': key, 'authorization': 'Bearer ' + key,
            'user-agent': 'claude-cli/2.1.114 (external, cli)'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode())
                u = d.get('usage') or {}
                print(f'  [OK ] {label:22s} out_tokens={u.get("output_tokens")}')
        except urllib.error.HTTPError as e:
            print(f'  [HTTP{e.code}] {label:22s} {e.read().decode()[:220]}'.replace('\n', ' '))
        except Exception as e:  # noqa: BLE001
            print(f'  [ERR] {label:22s} {type(e).__name__} {str(e)[:120]}')
