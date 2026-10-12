# -*- coding: utf-8 -*-
"""打包 FIN3-WKN-150 第五轮 fix7 批次与拆分附件。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix7-150"
SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}
MODE_DIR = 0o40755
MODE_EXEC = 0o100755
MODE_FILE = 0o100644
EXEC_SUFFIX = {".sh"}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def collect(source: pathlib.Path, arc_prefix: str) -> tuple[list[tuple[pathlib.Path, str]], list[str]]:
    files: list[tuple[pathlib.Path, str]] = []
    dirs: list[str] = []
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        relative_dir = pathlib.Path(dirpath).relative_to(source)
        if str(relative_dir) != ".":
            dirs.append(f"{arc_prefix}/{relative_dir.as_posix()}/")
        for name in sorted(filenames):
            if name in SKIP_FILES or pathlib.Path(name).suffix in SKIP_EXT:
                continue
            path = pathlib.Path(dirpath) / name
            relative = path.relative_to(source)
            files.append((path, f"{arc_prefix}/{relative.as_posix()}"))
    return files, dirs


def write_zip(output: pathlib.Path, files: list[tuple[pathlib.Path, str]],
              dirs: list[str], arc_root: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for arc in sorted(dirs):
            info = zipfile.ZipInfo(arc)
            info.external_attr = (MODE_DIR << 16) | 0x10
            archive.writestr(info, b"")
        for path, arc in files:
            mode = MODE_EXEC if path.suffix in EXEC_SUFFIX else MODE_FILE
            info = zipfile.ZipInfo(arc, date_time=(2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = mode << 16
            archive.writestr(info, path.read_bytes())
    validate_zip(output, arc_root)


def validate_zip(path: pathlib.Path, expected_task_dir: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        infos = {info.filename: info for info in archive.infolist()}
    tops = sorted({name.split("/")[0] for name in names})
    second = sorted({name.split("/")[1] for name in names
                     if name.count("/") >= 1 and name.split("/")[1]})
    leaked = [name for name in names
              if "_rejudge" in name or "__pycache__" in name
              or name.endswith((".pyc", ".out", ".err"))]
    crlf = [name for name in names
            if name.endswith((".sh", ".py", ".toml", ".md"))
            and b"\r\n" in zipfile.ZipFile(path).read(name)]
    modes = {(name, (infos[name].external_attr >> 16) & 0o777)
             for name in names if not name.endswith("/")}
    sh_modes = {name: mode for name, mode in modes if name.endswith(".sh")}
    other_modes = sorted({mode for name, mode in modes if not name.endswith(".sh")})
    print(f"zip      : {path}")
    print(f"size     : {path.stat().st_size} B")
    print(f"sha256   : {sha256(path)}")
    print(f"entries  : {len(names)}")
    print(f"tops     : {tops}")
    print(f"second   : {second}")
    print(f"leaked   : {leaked or 'none'}")
    print(f"crlf     : {crlf or 'none'}")
    print(f"sh modes : {sh_modes}")
    print(f"other    : {other_modes}")
    print(f"checks   : tops={len(tops)} second_ok={TASK in second} "
          f"leaked={len(leaked)} crlf={len(crlf)}")
    if len(tops) != 1 or TASK not in second or leaked or crlf:
        raise SystemExit("zip validation failed")
    if any((mode & 0o777) != 0o755 for mode in sh_modes.values()) or other_modes != [0o644]:
        raise SystemExit("zip permission validation failed")
    print("zip validation passed")


def build_task_answer(out_dir: pathlib.Path) -> None:
    task_source = H / BATCH / TASK
    files, dirs = collect(task_source, TASK)
    write_zip(out_dir / f"{TASK}_task.zip", files, dirs, TASK)

    answer_root = out_dir / "_answer_root" / TASK
    if answer_root.exists():
        import shutil
        shutil.rmtree(answer_root)
    answer_root.mkdir(parents=True)
    solution_src = task_source / "solution"
    shutil_copy = __import__("shutil").copytree
    shutil_copy(solution_src, answer_root / "solution")
    shutil_copy(task_source / "tests" / "__golden_output", answer_root / "tests" / "__golden_output")
    answer_files, answer_dirs = collect(answer_root, TASK)
    write_zip(out_dir / f"{TASK}_answer.zip", answer_files, answer_dirs, TASK)
    import shutil
    shutil.rmtree(answer_root.parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(H))
    args = parser.parse_args()
    out_dir = pathlib.Path(args.out)
    batch_dir = H / BATCH
    if not (batch_dir / TASK).is_dir():
        raise SystemExit(f"missing {batch_dir / TASK}")
    write_zip(out_dir / f"{BATCH}.zip", *collect(batch_dir, BATCH), BATCH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
