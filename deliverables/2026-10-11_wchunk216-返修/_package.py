"""Package the repaired delivery zip and record its digest.

Layout (unchanged from the version that was reviewed, plus the verifier-side
sibling):

  outside_harbor/<task-id>.json
  outside_harbor-assets/<task-id>/...        agent-visible
  outside_harbor-verifier/<task-id>/...      injected at grading time only
  jobs/...                                   run evidence
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
BUILD = ROOT / "build"
OUT = ROOT / "package"
TASK_ID = "wfflab__wchunk-216"
VERSION = "1.2.0"
ZIP_NAME = f"{TASK_ID}-v{VERSION}-delivery.zip"

ROOTS = ["outside_harbor", "outside_harbor-assets", "outside_harbor-verifier", "jobs"]
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", "results", "logs"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
# Already-compressed payloads: store them instead of deflating again.
STORE_SUFFIXES = {".zip", ".whl", ".png", ".jpg", ".jpeg", ".gz", ".7z", ".exe"}


def iter_members():
    for root in ROOTS:
        base = BUILD / root
        if not base.exists():
            raise SystemExit(f"missing package root: {base}")
        for path in sorted(base.rglob("*")):
            if path.is_dir():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(BUILD).parts):
                continue
            if path.name in SKIP_FILES:
                continue
            yield path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / ZIP_NAME
    if target.exists():
        target.unlink()

    count = 0
    total = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in iter_members():
            rel = path.relative_to(BUILD).as_posix()
            method = (zipfile.ZIP_STORED if path.suffix.lower() in STORE_SUFFIXES
                      else zipfile.ZIP_DEFLATED)
            archive.write(path, rel, compress_type=method)
            count += 1
            total += path.stat().st_size
            if count % 25 == 0:
                print(f"  packed {count} files...", flush=True)

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / f"{ZIP_NAME}.sha256").write_text(f"{digest}  {ZIP_NAME}\n", encoding="ascii")

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
    print(f"zip     : {target}")
    print(f"entries : {count} (namelist {len(names)})")
    print(f"raw     : {total / 1048576:.1f} MiB")
    print(f"zip     : {target.stat().st_size / 1048576:.1f} MiB")
    print(f"sha256  : {digest}")


if __name__ == "__main__":
    sys.exit(main())
