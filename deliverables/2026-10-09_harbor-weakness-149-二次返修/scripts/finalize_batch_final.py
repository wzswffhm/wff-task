# -*- coding: utf-8 -*-
"""打破文档自指大小振荡：交付物行改为「约值 + 以飞书实测为准」，再打最终包。"""
import collections
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
BATCH_NAME = 'work_fin-b01_20261009_fix8-149'
ROOT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
SRC = ROOT / BATCH_NAME
OUT = ROOT / f'{BATCH_NAME}.zip'
DOC = SRC / 'FIN3-WKN-149' / '交付文档.md'
EXCLUDE_DIRS = {'__pycache__', '_prev', '.git', '.pytest_cache'}

old = re.compile(r'（\*\*[\d,]+ B\*\*，单一附件）')
t = DOC.read_bytes().decode('utf-8')
m = old.search(t)
assert m, '未找到交付物行的大小串'
new = ('（**约 16.06 MB**，单一附件；精确字节数以飞书附件字段实测为准——'
       '交付文档自身入包，自指大小存在 ±1 B 压缩舍入，故此处不写死精确值）')
DOC.write_bytes((t[:m.start()] + new + t[m.end():]).encode('utf-8'))
print('[OK] 已改为约值表述:', new[:60], '...')


def mode_of(p):
    if p.is_dir():
        return 0o40755
    return 0o100755 if p.suffix == '.sh' else 0o100644


dirs, files = [], []
for p in sorted(SRC.rglob('*')):
    if any(part in EXCLUDE_DIRS for part in p.parts):
        continue
    if p.suffix == '.pyc' or p.name == '.DS_Store':
        continue
    rel = f'{BATCH_NAME}/' + p.relative_to(SRC).as_posix()
    (dirs if p.is_dir() else files).append((rel + ('/' if p.is_dir() else ''), p))
dirs.sort(key=lambda e: e[0])
files.sort(key=lambda e: e[0])
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    zi = zipfile.ZipInfo(f'{BATCH_NAME}/')
    zi.external_attr = (0o40755 << 16) | 0x10
    zi.compress_type = zipfile.ZIP_STORED
    zf.writestr(zi, b'')
    for arc, _ in dirs:
        if arc == f'{BATCH_NAME}/':
            continue
        zi = zipfile.ZipInfo(arc)
        zi.external_attr = (0o40755 << 16) | 0x10
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, b'')
    for arc, src in files:
        zi = zipfile.ZipInfo(arc)
        zi.external_attr = mode_of(src) << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, src.read_bytes())

info = zipfile.ZipFile(OUT).infolist()
modes = collections.Counter(oct(x.external_attr >> 16) for x in info)
bad = [x.filename for x in info
       if not x.filename.endswith('/') and (x.external_attr >> 16) not in (0o100644, 0o100755)]
print(f'[OK] 最终 {OUT.name}: {len(info)} 条目, {OUT.stat().st_size:,} B ({OUT.stat().st_size / 1048576:.2f} MiB)')
print(f'    权限: {dict(modes)}   异常: {bad or "无"}')
print(f'    顶层: {sorted({x.filename.split("/")[0] for x in info})}')
print(f'    含跑分产物 summary.json: {any("跑分产物与轨迹/summary.json" in x.filename for x in info)}')
print(f'    含交付文档: {any(x.filename.endswith("FIN3-WKN-149/交付文档.md") for x in info)}')
