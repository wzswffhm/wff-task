"""Convert the cached Docker manifest into an OCI-shaped one and rebuild the layout.

docker load accepts an OCI layout, but the manifest and config descriptors must
carry OCI media types; a Docker-schema manifest inside an OCI index is rejected
with "does not contain a manifest.json". This rewrites the descriptors, keeps the
layer bytes untouched (they are already OCI-compatible gzip layers), and rebuilds
index.json.
"""

import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DOCKER_MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
DOCKER_CONFIG = "application/vnd.docker.container.image.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
DOCKER_LAYER = "application/vnd.docker.image.rootfs.diff.tar.gzip"
OCI_LAYER = "application/vnd.oci.image.layer.v1.tar+gzip"

CONFIG_MAP = {DOCKER_CONFIG: OCI_CONFIG, OCI_CONFIG: OCI_CONFIG}
LAYER_MAP = {DOCKER_LAYER: OCI_LAYER, OCI_LAYER: OCI_LAYER}


def main():
    src_manifest = os.path.join(HERE, "image-manifest.json")
    layout = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Downloads\oci-layout-wserver"
    reference = "mcr.microsoft.com/windows/server:ltsc2022"

    with open(src_manifest, "r", encoding="utf-8-sig") as handle:
        docker_manifest = json.load(handle)

    blobs = os.path.join(layout, "blobs", "sha256")
    if not os.path.isdir(blobs):
        print("no blobs directory at", blobs)
        return 1

    oci_manifest = {
        "schemaVersion": 2,
        "mediaType": OCI_MANIFEST,
        "config": {
            "mediaType": CONFIG_MAP.get(docker_manifest["config"]["mediaType"], OCI_CONFIG),
            "digest": docker_manifest["config"]["digest"],
            "size": docker_manifest["config"]["size"],
        },
        "layers": [
            {
                "mediaType": LAYER_MAP.get(layer.get("mediaType", ""), OCI_LAYER),
                "digest": layer["digest"],
                "size": layer["size"],
            }
            for layer in docker_manifest["layers"]
        ],
    }

    # Windows images carry an os.version in the platform descriptor; keep it.
    if "annotations" in docker_manifest:
        oci_manifest["annotations"] = docker_manifest["annotations"]

    manifest_bytes = json.dumps(oci_manifest, separators=(",", ":")).encode("utf-8")
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_path = os.path.join(blobs, manifest_digest)
    with open(manifest_path, "wb") as handle:
        handle.write(manifest_bytes)
    print("wrote OCI manifest:", manifest_digest)

    # Drop the stale Docker-schema manifest blob so the layout only carries the
    # descriptors index.json actually references.
    for name in os.listdir(blobs):
        if name == manifest_digest:
            continue
        path = os.path.join(blobs, name)
        if os.path.getsize(path) < 4096:
            with open(path, "rb") as handle:
                head = handle.read(200)
            if b'"mediaType":"application/vnd.docker.distribution.manifest.v2+json"' in head:
                os.remove(path)
                print("removed stale docker manifest blob:", name)

    with open(os.path.join(layout, "oci-layout"), "w", encoding="utf-8") as handle:
        json.dump({"imageLayoutVersion": "1.0.0"}, handle, separators=(",", ":"))

    index = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": OCI_MANIFEST,
                "digest": "sha256:" + manifest_digest,
                "size": len(manifest_bytes),
                "platform": {"architecture": "amd64", "os": "windows", "os.version": "10.0.20348.5761"},
                "annotations": {"org.opencontainers.image.ref.name": reference},
            }
        ],
    }
    with open(os.path.join(layout, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2)

    print("index.json rewritten for", reference)
    print("blobs now:")
    for name in sorted(os.listdir(blobs)):
        print("  %s  %d B" % (name, os.path.getsize(os.path.join(blobs, name))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
