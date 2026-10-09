# -*- coding: utf-8 -*-
"""重建飞书用的两个附件包（保持既有目录层级与权限位口径）：
  FIN3-WKN-149_task.zip    = 题包（instruction/task.toml/rubrics.json/environment/tests，不含 solution）
  FIN3-WKN-149_answer.zip  = 标准答案（solution/{solve.sh,golden_output/*} + tests/__golden_output/*）
"""
import pathlib
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task')
PKG = ROOT / 'harbor-weakness' / 'FIN3-WKN-149'
TASK_ZIP = ROOT / 'harbor-weakness' / 'FIN3-WKN-149_task.zip'
ANS_ZIP = ROOT / 'harbor-weakness' / 'FIN3-WKN-149_answer.zip'
BAK = ROOT / 'deliverables' / '2026-10-09_harbor-weakness-149-二次返修' / '_backup_zips'
TOPDIR = 'FIN3-WKN-149'

TASK_ITEMS = ['instruction.md', 'rubrics.json', 'task.toml', 'environment', 'tests']
# tests/ 只放 4 个平台文件；__golden_output/ 属标准答案包，不进题目包
TASK_EXCLUDE_DIRS = {'tests/__golden_output'}
ANS_ITEMS = ['solution', 'tests/__golden_output']
ANS_EXTRA_DIRS = ['tests']          # answer 包里 tests/ 仅作为 __golden_output 的父目录出现


def mode_of(p: pathlib.Path) -> int:
    if p.is_dir():
        return 0o40755
    return 0o100755 if p.suffix == '.sh' else 0o100644


def build(zip_path: pathlib.Path, items, extra_dirs=(), exclude_dirs=()):
    if zip_path.exists() and not (BAK / zip_path.name).exists():
        BAK.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, BAK / zip_path.name)
    entries = []          # (arcname, abs_path or None)
    entries.append((f'{TOPDIR}/', None))
    for d in extra_dirs:
        entries.append((f'{TOPDIR}/{d}/', PKG / d))
    for it in items:
        p = PKG / it
        if p.is_dir():
            entries.append((f'{TOPDIR}/{it}/', p))
            for sub in sorted(p.rglob('*')):
                if '__pycache__' in sub.parts or sub.name.endswith('.pyc'):
                    continue
                rel = sub.relative_to(PKG).as_posix()
                if any(rel == e or rel.startswith(e + '/') for e in exclude_dirs):
                    continue
                entries.append((f'{TOPDIR}/{rel}{"/" if sub.is_dir() else ""}', sub))
        elif p.is_file():
            entries.append((f'{TOPDIR}/{it}', p))
    # 目录在前（按路径长度），文件在后
    dirs = [e for e in entries if e[0].endswith('/')]
    files = [e for e in entries if not e[0].endswith('/')]
    dirs.sort(key=lambda e: e[0])
    files.sort(key=lambda e: e[0])

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arc, src in dirs:
            zi = zipfile.ZipInfo(arc)
            zi.external_attr = (0o40755 << 16) | 0x10
            zi.compress_type = zipfile.ZIP_STORED
            zf.writestr(zi, b'')
        for arc, src in files:
            zi = zipfile.ZipInfo(arc)
            zi.external_attr = mode_of(src) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, src.read_bytes())
    return len(dirs) + len(files)


n1 = build(TASK_ZIP, TASK_ITEMS, exclude_dirs=TASK_EXCLUDE_DIRS)
n2 = build(ANS_ZIP, ANS_ITEMS, extra_dirs=ANS_EXTRA_DIRS)
print(f'{TASK_ZIP.name}: {n1} entries, {TASK_ZIP.stat().st_size:,} B')
print(f'{ANS_ZIP.name}: {n2} entries, {ANS_ZIP.stat().st_size:,} B')

# 自检
for zp in [TASK_ZIP, ANS_ZIP]:
    zf = zipfile.ZipFile(zp)
    bad = [i.filename for i in zf.infolist()
           if not i.filename.endswith('/') and (i.external_attr >> 16) not in (0o100644, 0o100755)]
    shs = [(i.filename, oct(i.external_attr >> 16)) for i in zf.infolist() if i.filename.endswith('.sh')]
    print(f'  {zp.name}: bad-mode={bad}  sh={shs}')
