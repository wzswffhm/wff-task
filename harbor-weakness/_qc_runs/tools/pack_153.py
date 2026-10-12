# -*- coding: utf-8 -*-
"""FIN3-WKN-153 打包：批次 zip + 题目附件 zip + 标准答案 zip。

- solve.sh / test.sh 显式写 0755（149 返修 #2 口径），create_system = 3（Unix）。
- 批次 zip 顶层为批次目录名，第二层为 {题目目录, 交付文档.md, 跑分产物与轨迹}
  （与 FIN3-WKN-151/152 一审通过结构一致）。
"""
import hashlib
import os
import pathlib
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-153"
BATCH_DIR = "work_fin-b01_20261012-153"
OUT = H / "_qc_runs" / "packages"

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git", ".venv"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}
EXEC_NAMES = {"solve.sh", "test.sh"}


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
    mode = 0o755 if src.name in EXEC_NAMES else 0o644
    zi = zipfile.ZipInfo(arc)
    zi.create_system = 3
    zi.external_attr = mode << 16
    zi.date_time = time.localtime(src.stat().st_mtime)[:6]
    zi.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(zi, src.read_bytes())


def write_dir(zf, arc: str):
    zi = zipfile.ZipInfo(arc)
    zi.create_system = 3
    zi.external_attr = (0o755 << 16) | 0x10
    zi.compress_type = zipfile.ZIP_STORED
    zf.writestr(zi, b"")


def pack_batch():
    batch_dir = H / BATCH_DIR
    out_zip = OUT / f"{BATCH_DIR}.zip"
    entries = [(rel, f"{BATCH_DIR}/{rel}") for rel, _p in walk(batch_dir)]
    with zipfile.ZipFile(out_zip, "w") as zf:
        for rel, arc in entries:
            write_entry(zf, batch_dir / rel, arc)
    return out_zip


def pack_task():
    td = H / BATCH_DIR / TASK
    out_zip = OUT / f"{TASK}_task.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("solution",)):
        if rel.startswith("tests/__golden_output"):
            continue
        entries.append((rel, f"{TASK}/{rel}"))
    with zipfile.ZipFile(out_zip, "w") as zf:
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            write_dir(zf, f"{d}/")
        for rel, arc in entries:
            write_entry(zf, td / rel, arc)
    return out_zip


def pack_answer():
    td = H / BATCH_DIR / TASK
    out_zip = OUT / f"{TASK}_answer.zip"
    entries = []
    for rel, p in walk(td, exclude_top=("environment",)):
        if rel.startswith("solution/") or rel.startswith("tests/__golden_output/"):
            entries.append((rel, f"{TASK}/{rel}"))
    with zipfile.ZipFile(out_zip, "w") as zf:
        dirs = sorted({a.rsplit("/", 1)[0] for _, a in entries if "/" in a})
        for d in dirs:
            write_dir(zf, f"{d}/")
        for rel, arc in entries:
            write_entry(zf, td / rel, arc)
    return out_zip


def report(z, label, want_top=None, expected_second=None):
    zf = zipfile.ZipFile(z)
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    leaked = [n for n in names if "_rejudge" in n or "__pycache__" in n
              or n.endswith((".pyc", ".out", ".err"))]
    files = [n for n in names if not n.endswith("/")]
    print(f"\n[{label}] {z.name}")
    print(f"  size   : {z.stat().st_size:,} B")
    print(f"  sha256 : {sha256(z)}")
    print(f"  entries: {len(names)}（文件 {len(files)} / 目录 {len(names) - len(files)}）")
    print(f"  顶层   : {tops}")
    print(f"  第二层 : {second}")
    print(f"  禁入项 : {leaked if leaked else '无'}")
    perm_bad = []
    for n in names:
        if n.endswith(("/solve.sh", "/test.sh")):
            mode = (zf.getinfo(n).external_attr >> 16) & 0o777
            if mode != 0o755:
                perm_bad.append((n, oct(mode)))
    print(f"  0755   : {'异常 ' + str(perm_bad) if perm_bad else 'solve.sh/test.sh 均 0755 OK'}")
    ok = not leaked and not perm_bad
    if want_top and tops != [want_top]:
        ok = False
    if expected_second:
        if want_top == BATCH_DIR:
            # 批次 zip：第二层 = 题目目录 + 交付文档.md（跑分归档存在时一并核对）
            need = {TASK, "交付文档.md"}
            if (H / BATCH_DIR / "跑分产物与轨迹").is_dir():
                need.add("跑分产物与轨迹")
        else:
            need = set(expected_second)
        if set(second) != need:
            ok = False
            print(f"  [!!] 第二层应为 {sorted(need)}，实际 {second}")
        else:
            print("  层级   : 第二层与期望一致 OK")
    print(f"  判定   : {'OK' if ok else '!! 异常'}")
    return ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    allok = True
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    if only in ("all", "batch"):
        allok &= report(pack_batch(), "批次 zip", want_top=BATCH_DIR,
                        expected_second=[TASK, "交付文档.md"])
    if only in ("all", "task"):
        allok &= report(pack_task(), "题目附件 task.zip", want_top=TASK,
                        expected_second=["environment", "instruction.md", "rubrics.json",
                                         "task.toml", "tests"])
        allok &= report(pack_answer(), "标准答案 answer.zip", want_top=TASK,
                        expected_second=["solution", "tests"])
    print("\n>>> " + ("全部通过" if allok else "存在问题"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
