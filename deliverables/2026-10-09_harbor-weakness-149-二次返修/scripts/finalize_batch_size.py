# -*- coding: utf-8 -*-
"""迭代回填批次包大小：使交付文档中的 SZ_BATCH 与最终 zip 实际大小一致（收敛即停）。"""
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


def mode_of(p):
    if p.is_dir():
        return 0o40755
    return 0o100755 if p.suffix == '.sh' else 0o100644


def pack():
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


PAT = re.compile(r'（\*\*[\d,]+ B\*\*，单一附件）')
for i in range(6):
    size = OUT.stat().st_size if OUT.exists() else 0
    t = DOC.read_bytes().decode('utf-8')
    m = PAT.search(t)
    want = f'（**{size:,} B**，单一附件）'
    if m and m.group(0) == want:
        print(f'[OK] 第 {i} 轮收敛：文档 = zip = {size:,} B')
        break
    if not m:
        print('[ERR] 未找到 SZ_BATCH 目标串')
        break
    DOC.write_bytes((t[:m.start()] + want + t[m.end():]).encode('utf-8'))
    pack()
    print(f'  轮 {i + 1}: 文档写入 {size:,} B -> 重打包后 {OUT.stat().st_size:,} B')
else:
    print('[WARN] 未在 6 轮内收敛')

info = zipfile.ZipFile(OUT).infolist()
modes = collections.Counter(oct(x.external_attr >> 16) for x in info)
bad = [x.filename for x in info
       if not x.filename.endswith('/') and (x.external_attr >> 16) not in (0o100644, 0o100755)]
print(f'[OK] 最终: {OUT.name}  {len(info)} 条目  {OUT.stat().st_size:,} B  权限 {dict(modes)}')
print(f'    异常权限: {bad or "无"}')
print(f'    顶层: {sorted({x.filename.split("/")[0] for x in info})}')
