# -*- coding: utf-8 -*-
"""按质检报告第 7/8 条口径重新打包 FIN3-WKN-150。

归档树（报告要求）：
    <批次目录>/
    └── FIN3-WKN-150/                ← 第二层唯一，就是题目目录
        ├── instruction.md / task.toml / rubrics.json / environment / solution / tests
        ├── 交付文档.md               ← 由批次级移入
        └── 跑分产物与轨迹/            ← 由批次级移入

排除：`_rejudge/`（判分暂存）、`__pycache__/`、`*.pyc`、`.DS_Store`、`*.out`、`*.err`。

用法：
    python repack_150.py --batch work-金融-私募股权投资-20261008 --out-dir <目录> [--name work_fin-b01_20261009_fix4-150]
"""
import argparse
import hashlib
import os
import pathlib
import zipfile

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
TASK = "FIN3-WKN-150"

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default="work-金融-私募股权投资-20261008")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", default=None, help="zip 顶层目录名/包名（不含 .zip）")
    args = ap.parse_args()

    batch_dir = H / args.batch
    if not batch_dir.is_dir():
        raise SystemExit(f"批次目录不存在: {batch_dir}")
    name = args.name or batch_dir.name
    task_dir = batch_dir / TASK
    if not task_dir.is_dir():
        raise SystemExit(f"批次内缺题目目录: {task_dir}")

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_zip = out_dir / f"{name}.zip"

    entries = []
    for dirpath, dirnames, filenames in os.walk(batch_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f in SKIP_FILES or pathlib.Path(f).suffix in SKIP_EXT:
                continue
            p = pathlib.Path(dirpath) / f
            rel = p.relative_to(batch_dir)
            entries.append((p, f"{name}/{rel.as_posix()}"))

    # 空目录也登记（保持结构，如 tests/__golden_output 之外的占位目录）
    for dirpath, dirnames, filenames in os.walk(batch_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if not dirnames and not filenames:
            rel = pathlib.Path(dirpath).relative_to(batch_dir)
            entries.append((pathlib.Path(dirpath), f"{name}/{rel.as_posix()}/"))

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, arc in entries:
            if p.is_dir():
                info = zipfile.ZipInfo(arc)
                info.external_attr = (0o40755 << 16) | 0x10
                zf.writestr(info, b"")
            else:
                zf.write(p, arc)

    names = zipfile.ZipFile(out_zip).namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    print(f"zip      : {out_zip}")
    print(f"size     : {out_zip.stat().st_size} B")
    print(f"sha256   : {sha256(out_zip)}")
    print(f"entries  : {len(names)}")
    print(f"顶层     : {tops}   （应为批次名，且唯一）")
    print(f"第二层   : {second}")
    leaked = [n for n in names if "/_rejudge/" in n or n.endswith(".pyc") or n.endswith(".out")]
    print(f"禁入项   : {leaked if leaked else '无'}")
    if len(tops) != 1 or TASK not in second:
        print("!! 结构不符合报告要求（顶层应唯一且第二层含题目目录）")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
