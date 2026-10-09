# -*- coding: utf-8 -*-
"""FIN3-WKN-150 第三轮（fix5）打包：批次 zip + task.zip + answer.zip。

批次 zip 结构（质检报告第 7 条）：
    work_fin-b01_20261006_fix5-150/
    └── FIN3-WKN-150/          ← 第二层唯一
        ├── 五件套 + 交付文档.md + 跑分产物与轨迹/

task.zip   = FIN3-WKN-150/{instruction.md,task.toml,rubrics.json,environment/,tests/（除 __golden_output）}
answer.zip = FIN3-WKN-150/{solution/,tests/__golden_output/}

排除：_rejudge / __pycache__ / *.pyc / *.out / *.err / .DS_Store
"""
import hashlib
import os
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-150"
BATCH = "work-金融-私募股权投资-20261008"
BATCH_ZIP_NAME = "work_fin-b01_20261006_fix5-150"
OUT = H  # 与既有 zip 同目录

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk(root, exclude_top=()):
    """产出 (相对路径, 绝对路径)，排除目录/文件。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in exclude_top)
        for f in sorted(filenames):
            if f in SKIP_FILES or pathlib.Path(f).suffix in SKIP_EXT:
                continue
            p = pathlib.Path(dirpath) / f
            yield p.relative_to(root).as_posix(), p


def pack_batch():
    batch_dir = H / BATCH
    task_dir = batch_dir / TASK
    out_zip = OUT / f"{BATCH_ZIP_NAME}.zip"
    entries = [(rel, f"{BATCH_ZIP_NAME}/{rel}") for rel, p in walk(batch_dir)]
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, arc in entries:
            zf.write(batch_dir / rel, arc)
    return out_zip, entries


def pack_task():
    """五件套（tests 排除 __golden_output）。"""
    td = H / TASK
    out_zip = OUT / f"{TASK}_task.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("solution",)):
        if rel.startswith("tests/__golden_output"):
            continue
        if rel.startswith("交付文档") or rel.startswith("跑分产物与轨迹") or rel.startswith("_rejudge"):
            continue
        entries.append((rel, f"{TASK}/{rel}"))
    # 空目录登记（environment/tests 顶层）
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 先写目录条目（与既有包一致的结构）
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            info = zipfile.ZipInfo(f"{TASK}/{d}/")
            info.external_attr = (0o40755 << 16) | 0x10
            zf.writestr(info, b"")
        zf.writestr(zipfile.ZipInfo(f"{TASK}/"), b"")
        for rel, arc in entries:
            zf.write(td / rel, arc)
    return out_zip, entries


def pack_answer():
    """solution/ + tests/__golden_output/。"""
    td = H / TASK
    out_zip = OUT / f"{TASK}_answer.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("environment",)):
        if rel.startswith("solution/") or rel.startswith("tests/__golden_output/"):
            entries.append((rel, f"{TASK}/{rel}"))
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            info = zipfile.ZipInfo(f"{TASK}/{d}/")
            info.external_attr = (0o40755 << 16) | 0x10
            zf.writestr(info, b"")
        zf.writestr(zipfile.ZipInfo(f"{TASK}/"), b"")
        for rel, arc in entries:
            zf.write(td / rel, arc)
    return out_zip, entries


def report(z, label, want_top=None, want_second=None):
    zf = zipfile.ZipFile(z)
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    leaked = [n for n in names if "/_rejudge/" in n or n.endswith(".pyc") or n.endswith(".out") or n.endswith(".err")]
    files = [n for n in names if not n.endswith("/")]
    print(f"\n[{label}] {z.name}")
    print(f"  size   : {z.stat().st_size:,} B")
    print(f"  sha256 : {sha256(z)}")
    print(f"  entries: {len(names)}（文件 {len(files)} / 目录 {len(names)-len(files)}）")
    print(f"  顶层   : {tops}")
    print(f"  第二层 : {second}")
    print(f"  禁入项 : {leaked if leaked else '无'}")
    ok = not leaked
    if want_top and tops != [want_top]:
        ok = False
    if want_second and want_second not in second:
        ok = False
    print(f"  判定   : {'OK' if ok else '!! 结构异常'}")
    return ok


def main():
    allok = True
    z1, e1 = pack_batch()
    allok &= report(z1, "批次 zip", want_top=BATCH_ZIP_NAME, want_second=TASK)
    z2, e2 = pack_task()
    allok &= report(z2, "题目附件 task.zip", want_top=TASK)
    z3, e3 = pack_answer()
    allok &= report(z3, "标准答案 answer.zip", want_top=TASK)
    print("\n>>> " + ("全部通过" if allok else "存在问题"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
