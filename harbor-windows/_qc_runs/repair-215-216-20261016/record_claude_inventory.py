# -*- coding: utf-8 -*-
"""把 vendor/claude-code 记进两包的 environment/vendor/INVENTORY.json。

目录级摘要：对所有文件按相对路径排序后计算 sha256（与 dirhash 同思路），
记录文件数与总字节数。
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
PKGS = ["wfflab__wsparse-215-v1.0.1-delivery", "wfflab__wvas-216-v1.0.1-delivery"]
VERSION = "2.1.301"


def digest(root: pathlib.Path) -> tuple[str, int, int]:
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    total = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        blob = path.read_bytes()
        total += len(blob)
        h.update(rel.encode("utf-8"))
        h.update(b"\t")
        h.update(hashlib.sha256(blob).hexdigest().encode("ascii"))
        h.update(b"\n")
    return h.hexdigest(), len(files), total


def main() -> int:
    for pkg in PKGS:
        inv_path = HW / pkg / "environment" / "vendor" / "INVENTORY.json"
        root = HW / pkg / "environment" / "vendor" / "claude-code"
        if not inv_path.is_file() or not root.is_dir():
            print("skip", pkg)
            continue
        doc = json.loads(inv_path.read_text(encoding="utf-8"))
        sha, count, total = digest(root)
        doc.setdefault("sources", {})[
            "claude-code/"
        ] = (f"npm install -g @anthropic-ai/claude-code@{VERSION} "
             "(registry.npmmirror.com); vendored so the image builds offline")
        files = [f for f in doc.get("files", []) if f.get("path") != "claude-code/"]
        files.append({
            "path": "claude-code/",
            "kind": "directory",
            "files": count,
            "size": total,
            "sha256": sha,
            "note": f"Claude Code {VERSION}; provides C:/node/claude.cmd inside the image",
        })
        doc["files"] = files
        inv_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        print(f"{pkg}: claude-code/ {count} files, {total/1048576:.1f} MB, dirhash={sha[:16]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
