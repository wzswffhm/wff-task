# -*- coding: utf-8 -*-
"""飞书当前题包（fix3）vs 本地 fix5：三个 zip 逐文件差异 + 版本号对比。只读。"""
import hashlib
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
FS = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\feishu-150-verify")


def hmap(z):
    m = {}
    with zipfile.ZipFile(z) as zf:
        for i in zf.infolist():
            if not i.is_dir():
                m[i.filename] = hashlib.sha256(zf.read(i.filename)).hexdigest()[:16]
    return m


def show(title, old, new):
    print("=" * 104)
    print(title)
    print("=" * 104)
    a, b = hmap(old), hmap(new)
    only_old = sorted(set(a) - set(b))
    only_new = sorted(set(b) - set(a))
    diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    print(f"  飞书 fix3: {old.name}  {old.stat().st_size:,} B  文件 {len(a)}")
    print(f"  本地 fix5: {new.name}  {new.stat().st_size:,} B  文件 {len(b)}")
    print(f"  仅飞书有 ({len(only_old)}):")
    for k in only_old:
        print(f"      - {k}")
    print(f"  仅本地有 ({len(only_new)}):")
    for k in only_new:
        print(f"      + {k}")
    print(f"  内容不同 ({len(diff)}):")
    for k in diff:
        print(f"      ~ {k}")
    print()
    return only_old, only_new, diff


def version_of(z, suffix):
    """从 zip 里读 task.toml 的 version。"""
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith(suffix):
                t = zf.read(n).decode("utf-8", "replace")
                m = re.search(r'^version = "([^"]+)"', t, re.M)
                if m:
                    return m.group(1), n
    return None, None


print("### 1) 题目附件 task.zip")
o1, n1, d1 = show("飞书 FIN3-WKN-150_task.zip  vs  本地 fix5 task.zip",
                  FS / "fs_150_task.zip", H / "FIN3-WKN-150_task.zip")

print("### 2) 标准答案 answer.zip")
o2, n2, d2 = show("飞书 FIN3-WKN-150_answer.zip  vs  本地 fix5 answer.zip",
                  FS / "fs_150_answer.zip", H / "FIN3-WKN-150_answer.zip")

print("### 3) 交付物批次 zip")
o3, n3, d3 = show("飞书 work_fin-b01_20261006_fix3-150.zip  vs  本地 fix5 批次 zip",
                  FS / "fs_150_delivery_fix3.zip", H / "work_fin-b01_20261006_fix5-150.zip")

print("=" * 104)
print("版本号对比")
print("=" * 104)
for lbl, z in [("飞书 task.zip", FS / "fs_150_task.zip"),
               ("本地 task.zip", H / "FIN3-WKN-150_task.zip"),
               ("飞书交付物 fix3", FS / "fs_150_delivery_fix3.zip"),
               ("本地批次 fix5", H / "work_fin-b01_20261006_fix5-150.zip")]:
    v, where = version_of(z, "/task.toml")
    print(f"  {lbl:<18} task.toml version = {v}   ({where})")

print()
print("=" * 104)
print("判据内容对比（R29/R30 是否已在本地包中收紧）")
print("=" * 104)
for lbl, z in [("飞书 task.zip", FS / "fs_150_task.zip"),
               ("本地 task.zip", H / "FIN3-WKN-150_task.zip")]:
    with zipfile.ZipFile(z) as zf:
        n = next(x for x in zf.namelist() if x.endswith("tests/rubrics.toml"))
        t = zf.read(n).decode("utf-8")
    print(f"  {lbl}: R29 量化拆解={'量化拆解' in t}   R30 跨期量化幅度={'跨期变化的量化幅度' in t}")

print()
print("=" * 104)
print("归档树对比（#7）")
print("=" * 104)
for lbl, z in [("飞书 fix3", FS / "fs_150_delivery_fix3.zip"),
               ("本地 fix5", H / "work_fin-b01_20261006_fix5-150.zip")]:
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    third_has_doc = any(n.split("/")[1] == "交付文档.md" for n in names if n.count("/") >= 1)
    has_reorg = any("/跑分产物与轨迹/" in n and n.split("/")[1] == "FIN3-WKN-150" for n in names if n.count("/") >= 2)
    print(f"  {lbl}: 顶层={tops}")
    print(f"        第二层={second}")
    print(f"        交付文档.md 在第二层(违规)={third_has_doc}   跑分产物已入题目目录={has_reorg}")
