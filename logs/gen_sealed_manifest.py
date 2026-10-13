# -*- coding: utf-8 -*-
"""gen_sealed_manifest.py -- 重新生成 verifier/SEALED_MANIFEST.json。

用法：
    python gen_sealed_manifest.py --task <包目录>

扫描 <包>/verifier/ 下所有文件（排除 __pycache__ / SEALED_MANIFEST.json 自身 /
临时目录），记录相对路径、sha256 与 size，按路径排序写回。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".pytest_cache", "_evidence-tmp"}
SKIP_NAMES = {"SEALED_MANIFEST.json"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    a = ap.parse_args()

    task = Path(a.task).resolve()
    verifier = task / "verifier"
    if not verifier.is_dir():
        print("FAIL: no verifier/ under %s" % task)
        return 2

    # 身份位用标准 TOML 解析器读取，避免手写正则漂移
    import tomllib
    with open(task / "task.toml", "rb") as handle:
        toml_doc = tomllib.load(handle)
    task_id = toml_doc["metadata"]["task_id"]
    version = toml_doc["task"]["version"]

    files = []
    for path in sorted(verifier.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(verifier)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        data = path.read_bytes()
        files.append({
            "path": str(rel).replace("\\", "/"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })

    manifest = {
        "task_id": task_id,
        "task_version": version,
        "note": "Verifier-side material. Never injected into the agent environment.",
        "files": files,
    }
    out = verifier / "SEALED_MANIFEST.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print("%s: %d files sealed (task_version=%s)" % (out, len(files), version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
