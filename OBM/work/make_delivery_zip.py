#!/usr/bin/env python3
"""Build the OBM delivery ZIP with forced executable bits for verifier entrypoints.

Windows CPython's os.chmod cannot set Unix exec bits, so archive_task() in the
official build_delivery_zip.py would store 0o666 and the zip-based check_package
gate would fail. This mirrors archive_task() but forces 0o755 for known
executable entrypoints, guaranteeing the verifier runs correctly under Docker.

Usage:
  make_delivery_zip.py <task-dir> <output-zip> [--final]
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import zipfile
from pathlib import Path

FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)

# Entrypoints that must be executable inside the container.
EXEC_RELS = {
    "sources/verifier/test.sh",
    "sources/verifier/grader.py",
}


def archive_task(task: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        root_name = task.name
        directory = zipfile.ZipInfo(f"{root_name}/", FIXED_ZIP_TIME)
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16
        bundle.writestr(directory, b"")
        for path in sorted(task.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise ValueError(f"正式题包不能包含符号链接：{path.relative_to(task)}")
            relative = path.relative_to(task).as_posix()
            archive_name = f"{root_name}/{relative}"
            if path.is_dir():
                mode = path.stat().st_mode
                info = zipfile.ZipInfo(archive_name.rstrip("/") + "/", FIXED_ZIP_TIME)
                info.external_attr = (stat.S_IFDIR | (mode & 0o7777)) << 16
                bundle.writestr(info, b"")
                continue
            if not path.is_file():
                raise ValueError(f"正式题包包含不支持的文件类型：{path.relative_to(task)}")
            mode = path.stat().st_mode & 0o7777
            if relative in EXEC_RELS:
                mode = 0o755
            info = zipfile.ZipInfo(archive_name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | mode) << 16
            bundle.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not task.is_dir():
        print(f"task dir not found: {task}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    archive_task(task, output)
    print(f"wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
