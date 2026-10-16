# -*- coding: utf-8 -*-
"""校验打包出的交付 ZIP 与题包目录逐文件一致（SHA256）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wspawn-218-v1.0.0-delivery"
ZIP = (ROOT / "harbor-windows" / "_qc_runs" / "wspawn-build" / "zip"
       / "wfflab__wspawn-218-v1.0.0-delivery.zip")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    local = {p.relative_to(PKG).as_posix(): sha_file(p)
             for p in sorted(PKG.rglob("*")) if p.is_file()}
    with zipfile.ZipFile(ZIP) as zf:
        roots = {i.filename.split("/", 1)[0] for i in zf.infolist()}
        packed = {}
        for info in zf.infolist():
            if info.filename.endswith("/"):
                continue
            rel = info.filename.split("/", 1)[1]
            packed[rel] = sha_bytes(zf.read(info))
    only_zip = sorted(set(packed) - set(local))
    only_local = sorted(set(local) - set(packed))
    diff = sorted(k for k in set(packed) & set(local) if packed[k] != local[k])
    result = {
        "zip": str(ZIP),
        "zip_sha256": sha_file(ZIP),
        "zip_bytes": ZIP.stat().st_size,
        "zip_roots": sorted(roots),
        "zip_files": len(packed),
        "local_files": len(local),
        "only_in_zip": only_zip,
        "only_in_local": only_local,
        "content_diff": diff,
        "identical": not (only_zip or only_local or diff) and roots == {PKG.name},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out = ZIP.parent / "zip-vs-package.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
