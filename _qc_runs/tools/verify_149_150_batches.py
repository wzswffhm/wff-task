# -*- coding: utf-8 -*-
"""核验 149/150 的两套批次目录哪份与飞书交付包 zip 逐字节一致。只读。

149 飞书交付物 = work_fin-b01_20261005_fix7-149.zip  (批次根同名目录)
150 飞书交付物 = work_fin-b01_20261006_fix3-150.zip
候选批次目录：work-金融-*（归档代号） vs work_fin-b01_*（原始代号）
"""
import hashlib
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")


def hzip(zf, name):
    x = hashlib.sha256()
    with zf.open(name) as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            x.update(c)
    return x.hexdigest()


def hfile(p):
    x = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            x.update(c)
    return x.hexdigest()


CASES = [
    ("149", "work_fin-b01_20261005_fix7-149.zip",
     ["work-金融-资产管理-20261008", "work_fin-b01_20261005_fix7-149"]),
    ("150", "work_fin-b01_20261006_fix3-150.zip",
     ["work-金融-私募股权投资-20261008", "work_fin-b01_20261006_fix3-150"]),
]

for task, zname, cands in CASES:
    zpath = W / zname
    print("=" * 100)
    print(f"FIN3-WKN-{task}   飞书交付物 = {zname}")
    if not zpath.is_file():
        print("  !! zip 不存在"); continue
    with zipfile.ZipFile(zpath) as zf:
        # 顶层根目录名
        roots = {n.split("/")[0] for n in zf.namelist() if "/" in n}
        root = sorted(roots)[0] if roots else ""
        zmap = {}
        for n in zf.namelist():
            if n.endswith("/") or not n.startswith(root + "/"):
                continue
            rel = n[len(root) + 1:]
            zmap[rel] = hzip(zf, n)
    print(f"  zip 根目录 = {root}/   文件 = {len(zmap)}")
    for c in cands:
        d = W / c
        if not d.is_dir():
            print(f"  [{c}] 不存在"); continue
        lmap = {}
        for q in d.rglob("*"):
            if q.is_file():
                rel = q.relative_to(d).as_posix()
                if "__pycache__" in rel or rel.endswith(".pyc"):
                    continue
                lmap[rel] = hfile(q)
        oz = sorted(set(zmap) - set(lmap)); ol = sorted(set(lmap) - set(zmap))
        df = sorted(k for k in set(zmap) & set(lmap) if zmap[k] != lmap[k])
        verdict = "★ 与飞书逐字节一致" if not (oz or ol or df) else "有差异"
        print(f"  [{c}]  {len(lmap)} 文件  ->  {verdict}")
        if oz:
            print(f"        仅 zip 有 ({len(oz)}): {oz[:6]}")
        if ol:
            print(f"        仅本地有 ({len(ol)}): {ol[:6]}")
        if df:
            print(f"        内容不同 ({len(df)}): {df[:6]}")
    print()
