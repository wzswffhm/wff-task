"""Download the offline build material for the wfmt-215 image.

Everything lands under <root>/build/outside_harbor-assets/wfflab__wfmt-215/environment/vendor/
so the Dockerfile can install it without any network access.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修")
VENDOR = ROOT / "build" / "outside_harbor-assets" / "wfflab__wfmt-215" / "environment" / "vendor"
WHEELS = VENDOR / "wheels"

DOWNLOADS = [
    (
        "python-3.12.9-embed-amd64.zip",
        "https://registry.npmmirror.com/-/binary/python/3.12.9/python-3.12.9-embed-amd64.zip",
    ),
    (
        "MinGit-2.56.0.2-64-bit.zip",
        "https://registry.npmmirror.com/-/binary/git-for-windows/v2.56.0.windows.2/MinGit-2.56.0.2-64-bit.zip",
    ),
]

WHEEL_REQS = [
    "pip",
    "setuptools",
    "wheel",
    "pytest==8.3.5",
    "pytest-json-report==1.5.0",
]

WHEEL_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, url: str) -> None:
    target = VENDOR / name
    if target.exists() and target.stat().st_size > 0:
        print(f"skip  {name} (exists, {target.stat().st_size} bytes)")
        return
    print(f"pull  {name} <- {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "wfmt-build/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, target.open("wb") as out:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print(f"done  {name} ({target.stat().st_size} bytes)")


def main() -> None:
    VENDOR.mkdir(parents=True, exist_ok=True)
    WHEELS.mkdir(parents=True, exist_ok=True)

    for name, url in DOWNLOADS:
        fetch(name, url)

    print("pull  wheels")
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--only-binary=:all:",
        "--index-url", WHEEL_INDEX,
        "--dest", str(WHEELS),
        *WHEEL_REQS,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    print(proc.stdout[-4000:])
    if proc.returncode != 0:
        print(proc.stderr[-4000:])
        raise SystemExit(f"pip download failed with {proc.returncode}")

    inventory = []
    for path in sorted(VENDOR.rglob("*")):
        if path.is_file():
            inventory.append({
                "path": str(path.relative_to(VENDOR)).replace("\\", "/"),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            })
    (VENDOR / "INVENTORY.json").write_text(
        json.dumps({"note": "Offline build material; pinned by sha256.", "files": inventory},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(item["size"] for item in inventory)
    print(f"inventory: {len(inventory)} files, {total / 1048576:.1f} MiB")


if __name__ == "__main__":
    main()
