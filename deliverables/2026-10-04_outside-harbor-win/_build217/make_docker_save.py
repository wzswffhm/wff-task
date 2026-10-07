#!/usr/bin/env python3
"""Convert the downloaded OCI layout into the legacy `docker save` format.

The classic Windows image store (windowsfilter) refuses OCI archives
("does not contain a manifest.json"), so the blobs are re-linked into the
manifest.json layout that `docker load` understands and packed into one tar.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

TAG = "mcr.microsoft.com/windows/servercore:ltsc2022"


def digest_of(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oci", required=True)
    parser.add_argument("--verify-diff-ids", action="store_true")
    args = parser.parse_args()

    oci = Path(args.oci).resolve()
    blobs = oci / "blobs" / "sha256"
    save = oci / "save"

    index = json.loads((oci / "index.json").read_text(encoding="utf-8"))
    manifest_hex = index["manifests"][0]["digest"].split(":", 1)[1]
    manifest = json.loads((blobs / manifest_hex).read_text(encoding="utf-8"))
    config_hex = manifest["config"]["digest"].split(":", 1)[1]
    config = json.loads((blobs / config_hex).read_text(encoding="utf-8"))

    if save.exists():
        shutil.rmtree(save)
    save.mkdir(parents=True)

    def link(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)

    link(blobs / config_hex, save / f"{config_hex}.json")

    layers = []
    for index_, layer in enumerate(manifest["layers"]):
        hexd = layer["digest"].split(":", 1)[1]
        link(blobs / hexd, save / hexd / "layer.tar")
        layers.append(f"{hexd}/layer.tar")
        if args.verify_diff_ids:
            expected = config["rootfs"]["diff_ids"][index_]
            print(f"layer {index_}: diff_id {expected[:23]} (compressed blob {layer['size'] / 1048576:.1f} MB)")

    (save / "manifest.json").write_text(
        json.dumps([{"Config": f"{config_hex}.json", "RepoTags": [TAG], "Layers": layers}], indent=2),
        encoding="utf-8",
    )
    (save / "repositories").write_text(
        json.dumps({"mcr.microsoft.com/windows/servercore": {"ltsc2022": config_hex}}, indent=2),
        encoding="utf-8",
    )

    archive = oci / "servercore-ltsc2022-save.tar"
    if archive.exists():
        archive.unlink()
    print(f"packing {archive.name} ...")
    with tarfile.open(archive, "w") as tar:
        for path in sorted(save.rglob("*")):
            tar.add(path, arcname=str(path.relative_to(save)))
    print(f"archive: {archive} ({archive.stat().st_size / 1048576:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
