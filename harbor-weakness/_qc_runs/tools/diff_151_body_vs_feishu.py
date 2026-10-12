# -*- coding: utf-8 -*-
"""对比飞书交付物 zip 内的 FIN3-WKN-151/ 与本仓库题包本体 harbor-weakness/FIN3-WKN-151/。

以及检查 _rejudge（返修重判工作目录）是否存在于本体、是否被 zip 收录。
只报告，不修改。
"""
import hashlib
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
ZIP = W / "work_fin-b01_20261006-151.zip"
BODY = W / "FIN3-WKN-151"
PREFIX = "work_fin-b01_20261006-151/FIN3-WKN-151/"


def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


zip_files = {}
with zipfile.ZipFile(ZIP) as zf:
    for info in zf.infolist():
        if info.is_dir() or not info.filename.startswith(PREFIX):
            continue
        zip_files[info.filename[len(PREFIX):]] = h(zf.read(info.filename))

body_files = {}
for p in BODY.rglob("*"):
    if p.is_file():
        body_files[p.relative_to(BODY).as_posix()] = h(p.read_bytes())

only_zip = sorted(set(zip_files) - set(body_files))
only_body = sorted(set(body_files) - set(zip_files))
diff = sorted(k for k in set(zip_files) & set(body_files) if zip_files[k] != body_files[k])

print(f"zip 内 FIN3-WKN-151/ : {len(zip_files)} 文件")
print(f"本地题包本体          : {len(body_files)} 文件")
print()
print(f"仅 zip 有（本体缺失）: {len(only_zip)}")
for k in only_zip[:40]:
    print(f"    + {k}")
print(f"仅本体有（zip 没有）  : {len(only_body)}")
for k in only_body[:40]:
    print(f"    - {k}")
print(f"内容不同              : {len(diff)}")
for k in diff[:60]:
    print(f"    ~ {k}")
print()

# _rejudge 状态
rj = BODY / "_rejudge"
print(f"本体 _rejudge 存在 = {rj.is_dir()}")
if rj.is_dir():
    n = sum(1 for p in rj.rglob("*") if p.is_file())
    print(f"    _rejudge 文件数 = {n}")
    inn = [k for k in body_files if k.startswith("_rejudge/")]
    print(f"    其中被计入本体文件数 = {len(inn)}")
    inzip = [k for k in zip_files if k.startswith("_rejudge/")]
    print(f"    zip 内 _rejudge 文件数 = {len(inzip)}")
