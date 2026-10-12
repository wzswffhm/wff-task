#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用 zip 打包器：以 Unix 权限语义写入（create_system=3 + 高位 mode），
确保 Linux 下实际解压得到 0755（脚本）/0644（普通文件）/0755（目录）。

用法:
  python pack_zip_unix.py batch <批次目录名>        # 打包 harbor-weakness/<name>/ -> <name>.zip
  python pack_zip_unix.py task                      # 打包 FIN3-WKN-149_task.zip
  python pack_zip_unix.py answer                    # 打包 FIN3-WKN-149_answer.zip
"""
import collections
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
EXCLUDE_DIRS = {'__pycache__', '_prev', '.git', '.pytest_cache'}
TOPDIR = 'FIN3-WKN-149'
# Unix: S_IFDIR|0755 / S_IFREG|0755 / S_IFREG|0644
D_MODE = 0o40755
F_MODE = 0o100644
X_MODE = 0o100755


def mode_of(p: pathlib.Path) -> int:
    if p.is_dir():
        return D_MODE
    return X_MODE if p.suffix == '.sh' else F_MODE


def _zi(arc: str, mode: int, is_dir: bool) -> zipfile.ZipInfo:
    zi = zipfile.ZipInfo(arc)
    zi.create_system = 3                     # 关键：Unix，使 Linux 解压器读取高位 mode
    zi.external_attr = (mode << 16) | (0x10 if is_dir else 0)
    zi.compress_type = zipfile.ZIP_STORED if is_dir else zipfile.ZIP_DEFLATED
    return zi


def write_zip(out: pathlib.Path, entries, topdir_entry: str):
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(_zi(topdir_entry, D_MODE, True), b'')
        for arc, src in entries:
            if src is None:
                zf.writestr(_zi(arc, D_MODE, True), b'')
            elif src.is_dir():
                zf.writestr(_zi(arc, D_MODE, True), b'')
            else:
                zf.writestr(_zi(arc, mode_of(src), False), src.read_bytes())


def build_batch(name: str) -> pathlib.Path:
    src = H / name
    out = H / f'{name}.zip'
    if not src.is_dir():
        raise SystemExit(f'批次目录不存在: {src}')
    entries = []
    for p in sorted(src.rglob('*')):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix == '.pyc' or p.name == '.DS_Store':
            continue
        rel = f'{name}/' + p.relative_to(src).as_posix()
        entries.append((rel + ('/' if p.is_dir() else ''), p))
    entries.sort(key=lambda e: (not e[0].endswith('/'), e[0]))
    write_zip(out, entries, f'{name}/')
    return out


PKG = H / TOPDIR
TASK_ITEMS = ['instruction.md', 'rubrics.json', 'task.toml', 'environment', 'tests']
TASK_EXCLUDE = {'tests/__golden_output'}
ANS_ITEMS = ['solution', 'tests/__golden_output']


def build_task() -> pathlib.Path:
    out = H / f'{TOPDIR}_task.zip'
    entries = []
    for it in TASK_ITEMS:
        p = PKG / it
        if p.is_dir():
            entries.append((f'{TOPDIR}/{it}/', p))
            for sub in sorted(p.rglob('*')):
                if '__pycache__' in sub.parts or sub.name.endswith('.pyc'):
                    continue
                rel = sub.relative_to(PKG).as_posix()
                if any(rel == e or rel.startswith(e + '/') for e in TASK_EXCLUDE):
                    continue
                entries.append((f'{TOPDIR}/{rel}{"/" if sub.is_dir() else ""}', sub))
        else:
            entries.append((f'{TOPDIR}/{it}', p))
    entries.sort(key=lambda e: (not e[0].endswith('/'), e[0]))
    write_zip(out, entries, f'{TOPDIR}/')
    return out


def build_answer() -> pathlib.Path:
    out = H / f'{TOPDIR}_answer.zip'
    entries = [(f'{TOPDIR}/tests/', PKG / 'tests')]
    for it in ANS_ITEMS:
        p = PKG / it
        if p.is_dir():
            entries.append((f'{TOPDIR}/{it}/', p))
            for sub in sorted(p.rglob('*')):
                if '__pycache__' in sub.parts or sub.name.endswith('.pyc'):
                    continue
                rel = sub.relative_to(PKG).as_posix()
                entries.append((f'{TOPDIR}/{rel}{"/" if sub.is_dir() else ""}', sub))
    entries.sort(key=lambda e: (not e[0].endswith('/'), e[0]))
    write_zip(out, entries, f'{TOPDIR}/')
    return out


def report(out: pathlib.Path):
    info = zipfile.ZipFile(out).infolist()
    modes = collections.Counter(
        (i.create_system, oct(i.external_attr >> 16)) for i in info)
    shs = [(i.filename, i.create_system, oct(i.external_attr >> 16))
           for i in info if i.filename.endswith('.sh')]
    print(f'{out.name}: {len(info)} 条目, {out.stat().st_size:,} B')
    print(f'  (create_system, mode) 分布: {dict(modes)}')
    for f, cs, m in shs:
        print(f'    .sh: create_system={cs}  mode={m}  {f}')
    bad = [i.filename for i in info if i.create_system != 3]
    print(f'  非 Unix(create_system!=3) 条目: {len(bad)}')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'batch':
        report(build_batch(sys.argv[2]))
    elif cmd == 'task':
        report(build_task())
    elif cmd == 'answer':
        report(build_answer())
    elif cmd == 'all':
        for f in (build_task(), build_answer(), build_batch(sys.argv[2])):
            report(f)
    else:
        raise SystemExit(__doc__)
