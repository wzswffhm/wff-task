#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包交付 zip：zip 顶层只保留单一同名目录 <package-root 的目录名>/。

用法：
    python -X utf8 pack_delivery_zip.py \
        --package-root <交付包目录> --out-dir <输出目录> [--zip-name x.zip]

与 _qc_runs/tools/pack_216_single_root.py 的口径一致（同样的跳过规则与
已压缩载荷直存策略），只是把源目录参数化，便于 215/216/218/219 共用。
"""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

STORE_SUFFIXES = {".zip", ".whl", ".png", ".jpg", ".jpeg", ".gz", ".7z", ".exe"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "results", "logs"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", required=True, help="交付包目录（其目录名会成为 zip 顶层）")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--zip-name", default=None)
    args = ap.parse_args()

    src = Path(args.package_root).resolve()
    if not src.is_dir():
        raise SystemExit(f"包目录不存在：{src}")
    root_name = src.name
    zip_name = args.zip_name or f"{root_name}.zip"
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / zip_name
    if target.exists():
        target.unlink()

    count = 0
    total = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(p for p in src.rglob("*") if p.is_file()):
            rel = path.relative_to(src)
            if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_FILES:
                continue
            method = (zipfile.ZIP_STORED if path.suffix.lower() in STORE_SUFFIXES
                      else zipfile.ZIP_DEFLATED)
            zf.write(path, f"{root_name}/{rel.as_posix()}", compress_type=method)
            count += 1
            total += path.stat().st_size

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (out / f"{zip_name}.sha256").write_text(f"{digest}  {zip_name}\n", encoding="ascii")

    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    tops = {n.split("/")[0] for n in names}
    print(f"src      : {src}")
    print(f"zip      : {target}")
    print(f"entries  : {count}")
    print(f"raw      : {total / 1048576:.1f} MiB")
    print(f"size     : {target.stat().st_size / 1048576:.1f} MiB")
    print(f"sha256   : {digest}")
    print(f"top-level: {sorted(tops)}")
    if tops != {root_name}:
        raise SystemExit(f"!! zip 顶层不是单一同名目录：{sorted(tops)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
