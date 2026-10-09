#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取 opus 试次结果事件全文 + 端点在用凭据探测。"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
LOG = pathlib.Path('/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/'
                   'FIN3-WKN-149__6AB4Ng8/agent/claude-code.txt')

print('=== opus 轨迹中全部 result 事件 ===')
for ln in LOG.read_text(encoding='utf-8', errors='ignore').splitlines():
    if '"type":"result"' not in ln:
        continue
    try:
        d = json.loads(ln)
    except Exception:  # noqa: BLE001
        continue
    print(json.dumps({k: d.get(k) for k in
                      ['subtype', 'is_error', 'api_error_status', 'duration_ms',
                       'num_turns', 'terminal_reason', 'total_cost_usd']}, ensure_ascii=False))
    print('  result 文本:', str(d.get('result'))[:900])
    print()

print('=== 末尾 api_error 细节 ===')
txt = LOG.read_text(encoding='utf-8', errors='ignore')
i = txt.rfind('api_error_status')
print(txt[max(0, i - 300): i + 700])
