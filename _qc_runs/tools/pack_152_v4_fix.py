# -*- coding: utf-8 -*-
"""FIN3-WKN-152 v4 打包（修复版）：solve.sh/test.sh 显式写 0755（149返修#2 口径）。
其余逻辑与 pack_152_v4.py 一致。
"""
import hashlib
import os
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-152"
BATCH_DIR = "work_fin-b01_20261009-152"
BATCH_ZIP_NAME = "work_fin-b01_20261009-152"
OUT = H / "_qc_runs" / "packages"

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}
EXEC_NAMES = {"solve.sh", "test.sh"}   # 必须 0755


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(root, exclude_top=()):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in exclude_top)
        for f in sorted(filenames):
            if f in SKIP_FILES or pathlib.Path(f).suffix in SKIP_EXT:
                continue
            p = pathlib.Path(dirpath) / f
            yield p.relative_to(root).as_posix(), p


def write_entry(zf, src: pathlib.Path, arc: str):
    """写入条目；可执行脚本设 0755，其余 0644（Unix 语义）。"""
    mode = 0o755 if src.name in EXEC_NAMES else 0o644
    data = src.read_bytes()
    zi = zipfile.ZipInfo(arc)
    zi.create_system = 3                     # Unix
    zi.external_attr = (mode << 16)          # 文件权限
    zi.date_time = src.stat().st_mtime_ns // 1_000_000_000 and (
        __import__("time").localtime(src.stat().st_mtime))[:6] or (2026, 10, 10, 0, 0, 0)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(zi, data)


def write_dir(zf, arc: str):
    zi = zipfile.ZipInfo(arc)
    zi.create_system = 3
    zi.external_attr = (0o755 << 16) | 0x10  # 目录
    zi.compress_type = zipfile.ZIP_STORED
    zf.writestr(zi, b"")


def pack_batch():
    batch_dir = H / BATCH_DIR
    out_zip = OUT / f"{BATCH_ZIP_NAME}.zip"
    entries = [(rel, f"{BATCH_ZIP_NAME}/{rel}") for rel, p in walk(batch_dir)]
    with zipfile.ZipFile(out_zip, "w") as zf:
        for rel, arc in entries:
            write_entry(zf, batch_dir / rel, arc)
    return out_zip, entries


def pack_task():
    td = H / TASK
    out_zip = OUT / f"{TASK}_task.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("solution",)):
        if rel.startswith("tests/__golden_output"):
            continue
        if rel.startswith("交付文档") or rel.startswith("跑分产物与轨迹") or rel.startswith("_rejudge"):
            continue
        entries.append((rel, f"{TASK}/{rel}"))
    with zipfile.ZipFile(out_zip, "w") as zf:
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            write_dir(zf, f"{TASK}/{d}/")
        write_dir(zf, f"{TASK}/")
        for rel, arc in entries:
            write_entry(zf, td / rel, arc)
    return out_zip, entries


def pack_answer():
    td = H / TASK
    out_zip = OUT / f"{TASK}_answer.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("environment",)):
        if rel.startswith("solution/") or rel.startswith("tests/__golden_output/"):
            entries.append((rel, f"{TASK}/{rel}"))
    with zipfile.ZipFile(out_zip, "w") as zf:
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            write_dir(zf, f"{TASK}/{d}/")
        write_dir(zf, f"{TASK}/")
        for rel, arc in entries:
            write_entry(zf, td / rel, arc)
    return out_zip, entries


def report(z, label, want_top=None, want_second=None):
    zf = zipfile.ZipFile(z)
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    leaked = [n for n in names
              if "_rejudge" in n or "__pycache__" in n
              or n.endswith(".pyc") or n.endswith(".out") or n.endswith(".err")]
    files = [n for n in names if not n.endswith("/")]
    print(f"\n[{label}] {z.name}")
    print(f"  size   : {z.stat().st_size:,} B")
    print(f"  sha256 : {sha256(z)}")
    print(f"  entries: {len(names)}（文件 {len(files)} / 目录 {len(names)-len(files)}）")
    print(f"  顶层   : {tops}")
    print(f"  第二层 : {second}")
    print(f"  禁入项 : {leaked if leaked else '无'}")
    perm_bad = []
    for n in names:
        if n.endswith("/solve.sh") or n.endswith("/test.sh"):
            mode = (zf.getinfo(n).external_attr >> 16) & 0o777
            if mode != 0o755:
                perm_bad.append((n, oct(mode)))
    print(f"  0755   : {'异常 ' + str(perm_bad) if perm_bad else 'solve.sh/test.sh 均 0755 ✓'}")
    ok = not leaked and not perm_bad
    if want_top and tops != [want_top]:
        ok = False
    if want_second:
        if label == "批次 zip":
            # 151（序号267，一审通过）口径：批次根三者平级
            expect = sorted([want_second, "交付文档.md", "跑分产物与轨迹"])
            if second != expect:
                ok = False
                print(f"  [!!] 第二层应为 {expect}（151 口径），实际 {second}")
            else:
                print(f"  151 口径: 第二层三者平级 ✓")
        elif want_second not in second:
            ok = False
    print(f"  判定   : {'OK' if ok else '!! 异常'}")
    return ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    allok = True
    z1, _ = pack_batch()
    allok &= report(z1, "批次 zip", want_top=BATCH_ZIP_NAME, want_second=TASK)
    z2, _ = pack_task()
    allok &= report(z2, "题目附件 task.zip", want_top=TASK, want_second=TASK)
    z3, _ = pack_answer()
    allok &= report(z3, "标准答案 answer.zip", want_top=TASK, want_second=TASK)
    print("\n>>> " + ("全部通过" if allok else "存在问题"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
