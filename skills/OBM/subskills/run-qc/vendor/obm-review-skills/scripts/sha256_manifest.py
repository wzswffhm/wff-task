#!/usr/bin/env python3
"""Generate a deterministic SHA-256 manifest for files under given paths."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(paths: list[Path], manifest: Path) -> list[Path]:
    files = set()
    for path in paths:
        if path.is_file():
            if path.suffix != ".pyc" and "__pycache__" not in path.parts:
                files.add(path.resolve())
        elif path.is_dir():
            for child in path.rglob("*"):
                if (child.is_file() and child.suffix != ".pyc"
                        and "__pycache__" not in child.parts):
                    files.add(child.resolve())
        else:
            raise ValueError(f"path does not exist: {path}")
    files.discard(manifest.resolve())
    return sorted(files, key=lambda item: str(item))


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a sorted SHA-256 manifest without modifying inputs."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to include")
    parser.add_argument(
        "--output",
        required=True,
        help="Manifest output path",
    )
    parser.add_argument(
        "--base",
        default=".",
        help="Base directory used for relative display paths",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = Path(args.base).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    paths = [Path(value).expanduser().resolve() for value in args.paths]
    files = collect_files(paths, output)

    lines = [
        f"{sha256_file(path)}  {display_path(path, base)}"
        for path in files
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"files={len(files)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
