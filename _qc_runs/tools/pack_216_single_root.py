"""打包 216 单根交付 zip（zip 顶层只有 wfflab__wchunk-216-v1.2.0-delivery/）。

用法：python -X utf8 pack_216_single_root.py
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

REWORK = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
DIST = REWORK / "dist" / "wfflab__wchunk-216-v1.2.0-delivery"
OUT = REWORK / "package"
ZIP_NAME = "wfflab__wchunk-216-v1.2.0-delivery.zip"
ROOT_NAME = DIST.name
# 已压缩的载荷直接存储，避免二次压缩浪费
STORE_SUFFIXES = {".zip", ".whl", ".png", ".jpg", ".jpeg", ".gz", ".7z", ".exe"}
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "results", "logs"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def main() -> int:
    if not DIST.is_dir():
        raise SystemExit(f"缺 dist 目录：{DIST}（先跑 build_216_dist.py）")
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / ZIP_NAME
    if target.exists():
        target.unlink()

    count = 0
    total = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(p for p in DIST.rglob("*") if p.is_file()):
            rel = path.relative_to(DIST)
            if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_FILES:
                continue
            method = (zipfile.ZIP_STORED if path.suffix.lower() in STORE_SUFFIXES
                      else zipfile.ZIP_DEFLATED)
            zf.write(path, f"{ROOT_NAME}/{rel.as_posix()}", compress_type=method)
            count += 1
            total += path.stat().st_size

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / f"{ZIP_NAME}.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="ascii")

    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    tops = {n.split("/")[0] for n in names}
    print(f"zip      : {target}")
    print(f"entries  : {count}")
    print(f"raw      : {total / 1048576:.1f} MiB")
    print(f"zip      : {target.stat().st_size / 1048576:.1f} MiB")
    print(f"sha256   : {digest}")
    print(f"top-level: {sorted(tops)}")
    if tops != {ROOT_NAME}:
        raise SystemExit(f"!! zip 顶层不是单一同名目录：{sorted(tops)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
