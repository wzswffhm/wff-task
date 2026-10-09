# -*- coding: utf-8 -*-
"""盘点全仓出现的 API key（只打印前缀指纹，不打印原文）。"""
import hashlib
import pathlib
import re

roots = [pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task"),
         pathlib.Path(r"C:\Users\Administrator\.workbuddy"),
         pathlib.Path(r"C:\Users\Administrator\.wff-creds")]
pat = re.compile(r"(OPUS_API_KEY|ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|SOTA_KEY[A-Z_]*|api_key)"
                 r"\s*[=:]\s*[\"']?(sk-[A-Za-z0-9\-_\.]{16,}|[A-Za-z0-9\-_]{24,})")
exts = ('.py', '.sh', '.env', '.local', '.yaml', '.yml', '.json', '.md', '.txt', '.key', '.ps1', '.toml')
seen = {}
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in exts or p.stat().st_size > 3_000_000:
            continue
        try:
            t = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for m in pat.finditer(t):
            k, v = m.group(1), m.group(2)
            h = hashlib.sha1(v.encode()).hexdigest()[:10]
            seen.setdefault((k, h), []).append(str(p))
for (k, h), v in sorted(seen.items()):
    print(f"{k:22s} {h} count={len(v):3d} eg={v[0][-95:]}")
