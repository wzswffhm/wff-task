"""Refresh vendor/INVENTORY.json from whatever is on disk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
VENDOR = ROOT / "build" / "outside_harbor-assets" / "wfflab__wchunk-216" / "environment" / "vendor"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    inventory = []
    for path in sorted(VENDOR.rglob("*")):
        if path.is_file() and path.name != "INVENTORY.json":
            inventory.append({
                "path": str(path.relative_to(VENDOR)).replace("\\", "/"),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            })
    payload = {
        "note": "Offline build material for environment/Dockerfile; pinned by sha256.",
        "sources": {
            "python-3.12.9-embed-amd64.zip": "https://registry.npmmirror.com/-/binary/python/3.12.9/python-3.12.9-embed-amd64.zip",
            "MinGit-2.56.0.2-64-bit.zip": "https://registry.npmmirror.com/-/binary/git-for-windows/v2.56.0.windows.2/MinGit-2.56.0.2-64-bit.zip",
            "wheels/": "pip download --only-binary=:all: --index-url https://pypi.tuna.tsinghua.edu.cn/simple",
        },
        "files": inventory,
    }
    (VENDOR / "INVENTORY.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(item["size"] for item in inventory)
    print(f"inventory: {len(inventory)} files, {total / 1048576:.1f} MiB")
    for item in inventory:
        print(f"  {item['size']:>10}  {item['path']}")


if __name__ == "__main__":
    main()
