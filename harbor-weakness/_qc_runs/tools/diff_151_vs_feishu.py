# -*- coding: utf-8 -*-
"""对比飞书交付物 zip（work_fin-b01_20261006-151.zip）与本地批次目录的逐文件差异。

zip 根 = work_fin-b01_20261006-151/，对应本地 harbor-weakness/work-金融-商业银行-20261008/。
只报告差异，不修改任何文件。
"""
import hashlib
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
ZIP = W / "work_fin-b01_20261006-151.zip"
LOCAL = W / "work-金融-商业银行-20261008"
PREFIX = "work_fin-b01_20261006-151/"


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---- zip 侧 ----------------------------------------------------------------
zip_files = {}
with zipfile.ZipFile(ZIP) as zf:
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if not name.startswith(PREFIX):
            continue
        rel = name[len(PREFIX):]
        zip_files[rel] = h(zf.read(name))

# ---- 本地侧 ----------------------------------------------------------------
local_files = {}
for p in LOCAL.rglob("*"):
    if p.is_file():
        local_files[p.relative_to(LOCAL).as_posix()] = h(p.read_bytes())

only_zip = sorted(set(zip_files) - set(local_files))
only_local = sorted(set(local_files) - set(zip_files))
diff = sorted(k for k in set(zip_files) & set(local_files) if zip_files[k] != local_files[k])

print(f"zip   : {ZIP.name}  {len(zip_files)} 个文件")
print(f"本地  : {LOCAL.name}  {len(local_files)} 个文件")
print()
print(f"仅在 zip 中（本地缺失）: {len(only_zip)}")
for k in only_zip[:60]:
    print(f"    + {k}")
print()
print(f"仅在本地（zip 里没有）: {len(only_local)}")
for k in only_local[:60]:
    print(f"    - {k}")
print()
print(f"两边都有但内容不同: {len(diff)}")
for k in diff[:80]:
    print(f"    ~ {k}")
print()

# ---- 按顶层目录归类 --------------------------------------------------------
def bucket(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1:
        return "(根级文件)"
    if parts[0] == "FIN3-WKN-151":
        return "FIN3-WKN-151/" + (parts[1] if len(parts) > 2 else "(顶层)")
    if parts[0] == "跑分产物与轨迹":
        return "跑分产物与轨迹/" + (parts[1] if len(parts) > 2 else "(顶层)")
    return parts[0]


allchange = only_zip + only_local + diff
if allchange:
    print("差异按区域归类:")
    buckets = {}
    for k in allchange:
        buckets.setdefault(bucket(k), []).append(k)
    for b in sorted(buckets):
        print(f"  {b}: {len(buckets[b])}")
else:
    print(">>> 完全一致：本地批次目录与飞书交付物逐字节相同")
