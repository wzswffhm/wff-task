"""Build a docker-save archive from the downloaded blobs.

Docker 29's `docker load` rejected both a Docker-schema manifest inside an OCI
index and the corrected OCI layout, always with "does not contain a
manifest.json". The accepted shape is the one `docker save` produces:

    manifest.json                  [{"Config": ..., "RepoTags": [...], "Layers": [...]}]
    <config>.json                  the image config
    <layer-id>/layer.tar           an UNCOMPRESSED layer tar
    <layer-id>/VERSION             "1.0"

The gzipped blobs therefore have to be expanded, which costs roughly 10 GB of
temporary space, so this runs one layer at a time and reports progress.
"""

import gzip
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def expand(gz_path, out_path):
    """Stream-decompress a .tar.gz blob into out_path."""
    total_in = os.path.getsize(gz_path)
    done = 0
    started = time.time()
    with gzip.open(gz_path, "rb") as src, open(out_path, "wb") as dst:
        while True:
            block = src.read(8 * 1024 * 1024)
            if not block:
                break
            dst.write(block)
            done += len(block)
            # The ratio between compressed input and output is unknown while
            # streaming, so report elapsed time and output size instead.
            if done % (512 * 1024 * 1024) < 8 * 1024 * 1024:
                mb = done / (1024 * 1024)
                print("      %8.0f MB written  (%.0fs)" % (mb, time.time() - started), flush=True)
    return os.path.getsize(out_path)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Downloads\wserver2022"
    out = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\Administrator\Downloads\docker-save-wserver"
    reference = sys.argv[3] if len(sys.argv) > 3 else "mcr.microsoft.com/windows/server:ltsc2022"

    with open(os.path.join(HERE, "image-manifest.json"), "r", encoding="utf-8-sig") as handle:
        manifest = json.load(handle)

    if os.path.isdir(out):
        print("removing previous", out)
        shutil.rmtree(out)
    os.makedirs(out)

    config_digest = manifest["config"]["digest"].split(":", 1)[1]
    config_name = config_digest + ".json"
    shutil.copy2(os.path.join(src, "config.json"), os.path.join(out, config_name))
    print("config ->", config_name)

    layers = []
    for index, layer in enumerate(manifest["layers"], start=1):
        hex_digest = layer["digest"].split(":", 1)[1]
        gz_path = None
        for name in os.listdir(src):
            if name.startswith("layer%d" % index) and name.endswith(".tar.gz"):
                gz_path = os.path.join(src, name)
                break
        if gz_path is None:
            print("cannot find a layer file for layer", index)
            return 1

        layer_dir = os.path.join(out, hex_digest)
        os.makedirs(layer_dir)
        target = os.path.join(layer_dir, "layer.tar")
        print("expanding layer %d (%s, %.0f MB compressed)"
              % (index, hex_digest[:16], os.path.getsize(gz_path) / (1024 * 1024)), flush=True)
        size = expand(gz_path, target)
        print("  -> %.0f MB uncompressed" % (size / (1024 * 1024)), flush=True)

        with open(os.path.join(layer_dir, "VERSION"), "w", encoding="utf-8") as handle:
            handle.write("1.0")
        layers.append("%s/layer.tar" % hex_digest)

    save_manifest = [{
        "Config": config_name,
        "RepoTags": [reference],
        "Layers": layers,
    }]
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(save_manifest, handle, indent=2)

    # docker save archives also carry repositories, which older tooling reads.
    with open(os.path.join(out, "repositories"), "w", encoding="utf-8") as handle:
        json.dump({reference.split(":")[0]: {reference.split(":")[1]: layers[-1].split("/")[0]}}, handle)

    print("docker-save tree written to", out)
    print("layers:", layers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
