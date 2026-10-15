"""Assemble downloaded mcr blobs into an OCI layout that `docker load` accepts.

Why this exists: the Docker daemon on this host pulls the 4 GB Windows Server
base image at roughly 0.23 MB/s, while a browser goes through the system proxy
and can be far faster. The blobs themselves are anonymously downloadable, so the
plan is to fetch them with a normal download tool and reassemble the image
locally.

Usage:
    python assemble_oci_layout.py --downloads <dir> --out <dir>

The script looks for the blobs by their sha256, verifies every digest before use,
and writes a layout that `docker load` can consume directly (Docker 25+ reads an
OCI layout tarball; we hand it the directory via a tarball produced afterwards).

Nothing is downloaded here; this only verifies and arranges local files.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys


def sha256_of(path, chunk=4 * 1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def candidate_files(root):
    """Every regular file under root, keyed by lowercase hex sha256 (lazy)."""
    found = []
    for base, _dirs, names in os.walk(root):
        for name in names:
            path = os.path.join(base, name)
            if os.path.isfile(path):
                found.append(path)
    return found


def locate(root, wanted_digest, wanted_size, index, cache):
    """Find a file under root whose sha256 matches, using a size-first filter."""
    hex_digest = wanted_digest.split(":", 1)[1]
    for path in index:
        if path in cache:
            continue
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        # A gzip blob is downloaded verbatim, so the size should match exactly.
        # Allow a small slack in case a tool added nothing but the OS rounded.
        if wanted_size and abs(size - wanted_size) > 0:
            continue
        actual = sha256_of(path)
        if actual == hex_digest:
            cache[path] = actual
            print("  matched %s -> %s" % (hex_digest[:16], path))
            return path
    # Second pass without the size filter, in case the tool renamed or wrapped.
    for path in index:
        if path in cache:
            continue
        actual = sha256_of(path)
        cache[path] = actual
        if actual == hex_digest:
            print("  matched %s -> %s (size differed, digest verified)" % (hex_digest[:16], path))
            return path
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", required=True, help="directory holding the downloaded blobs")
    parser.add_argument("--out", required=True, help="directory to write the OCI layout into")
    parser.add_argument("--manifest", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                           "image-manifest.json"))
    parser.add_argument("--reference", default="mcr.microsoft.com/windows/server:ltsc2022")
    args = parser.parse_args()

    # PowerShell's Set-Content -Encoding UTF8 writes a BOM; tolerate it.
    with open(args.manifest, "r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)

    blobs_dir = os.path.join(args.out, "blobs", "sha256")
    os.makedirs(blobs_dir, exist_ok=True)

    index = candidate_files(args.downloads)
    print("scanned %d files under %s" % (len(index), args.downloads))
    if not index:
        print("NOTHING TO DO: no files found in the download directory")
        return 2

    cache = {}
    plan = []
    # config first (tiny), then layers
    plan.append(("config", manifest["config"]["digest"], manifest["config"].get("size", 0)))
    for layer in manifest["layers"]:
        plan.append(("layer", layer["digest"], layer.get("size", 0)))

    resolved = []
    for kind, digest, size in plan:
        path = locate(args.downloads, digest, size, index, cache)
        if path is None:
            print("MISSING %s %s (%d bytes)" % (kind, digest, size))
            return 1
        resolved.append((kind, digest, size, path))

    # Lay the blobs out by digest. Hard-link when possible so we do not duplicate
    # several gigabytes on a disk that is already tight.
    for kind, digest, size, path in resolved:
        target = os.path.join(blobs_dir, digest.split(":", 1)[1])
        if os.path.exists(target):
            os.remove(target)
        try:
            os.link(path, target)
            how = "hardlink"
        except OSError:
            shutil.copy2(path, target)
            how = "copy"
        print("  %-7s %s (%s)" % (kind, digest[:16], how))

    # The image manifest itself goes into blobs and is referenced by index.json.
    manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    with open(os.path.join(blobs_dir, manifest_digest), "wb") as handle:
        handle.write(manifest_bytes)

    with open(os.path.join(args.out, "oci-layout"), "w", encoding="utf-8") as handle:
        json.dump({"imageLayoutVersion": "1.0.0"}, handle)

    index_doc = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": manifest.get("mediaType", "application/vnd.docker.distribution.manifest.v2+json"),
                "digest": "sha256:" + manifest_digest,
                "size": len(manifest_bytes),
                "annotations": {"org.opencontainers.image.ref.name": args.reference},
            }
        ],
    }
    with open(os.path.join(args.out, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index_doc, handle, indent=2)

    print("layout written to %s" % args.out)
    print("next: docker load -i <tarball of that directory>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
