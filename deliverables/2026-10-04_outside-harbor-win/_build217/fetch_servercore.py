#!/usr/bin/env python3
"""Fetch mcr.microsoft.com/windows/servercore:ltsc2022 through a fast mirror and
assemble a local OCI image layout, so the image can be installed with a single
`docker load` instead of a multi-hour registry pull.

The Docker daemon on this host transfers ~230 KB/s from the registry while plain
HTTP clients reach 2+ MB/s from the same mirror, so the blobs are downloaded with
parallel range requests and verified against their content digests.

Usage:
    python fetch_servercore.py --out <dir> [--chunks 14]
    docker load -i <dir>/servercore-ltsc2022-oci.tar
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from pathlib import Path

REPO = "windows/servercore"
REF = "ltsc2022"
PLATFORM = {"architecture": "amd64", "os": "windows", "os.version": "10.0.20348.5622"}

REGISTRIES = [
    {
        "name": "daocloud",
        "registry": "https://mcr.m.daocloud.io",
        "token": "https://m.daocloud.io/auth/token?service=mcr.m.daocloud.io"
                 "&scope=repository:windows/servercore:pull",
    },
    {
        "name": "mcr-direct",
        "registry": "https://mcr.microsoft.com",
        "token": None,
    },
]

PRINT_LOCK = threading.RLock()


def say(message: str) -> None:
    with PRINT_LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def curl_get(url: str, headers: dict | None = None, dest: Path | None = None) -> bytes:
    """Fetch a URL with curl.

    curl drops the Authorization header when a registry redirects to a storage
    backend, which urllib would forward and turn into a 403.
    """
    args = ["curl", "-sSL", "--fail", "--retry", "3", "--retry-delay", "2", "--max-time", "180"]
    for key, value in (headers or {}).items():
        args += ["-H", f"{key}: {value}"]
    if dest is not None:
        args += ["-o", str(dest)]
    args.append(url)
    proc = subprocess.run(args, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl {url} failed ({proc.returncode}): {proc.stderr.decode('utf-8', 'replace')[:300]}")
    return proc.stdout


def http_json(url: str, headers: dict | None = None) -> dict:
    return json.loads(curl_get(url, headers).decode("utf-8"))


def http_bytes(url: str, headers: dict | None = None) -> bytes:
    return curl_get(url, headers)


def fetch_token(entry: dict) -> str:
    if not entry["token"]:
        return ""
    for attempt in range(4):
        try:
            return http_json(entry["token"])["token"]
        except Exception as exc:  # noqa: BLE001
            say(f"token attempt {attempt + 1} failed: {exc}")
            time.sleep(3)
    raise RuntimeError(f"cannot obtain a token from {entry['token']}")


def auth_headers(entry: dict, token: str) -> dict:
    headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def curl_range(url: str, headers: dict, start: int, end: int, dest: Path) -> None:
    args = [
        "curl", "-sSL", "--fail", "--retry", "3", "--retry-delay", "2",
        "--max-time", "1800", "-r", f"{start}-{end}",
    ]
    for key, value in headers.items():
        args += ["-H", f"{key}: {value}"]
    args += ["-w", "%{http_code}", "-o", str(dest), url]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed ({proc.returncode}): {proc.stderr.strip()[:300]}")
    code = proc.stdout.strip()
    expected = end - start + 1
    size = dest.stat().st_size
    if code != "206" and not (code == "200" and start == 0):
        raise RuntimeError(f"unexpected HTTP {code} for range {start}-{end}")
    if size != expected:
        raise RuntimeError(f"short read for range {start}-{end}: {size} != {expected}")


def digest_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download_blob(entry: dict, digest: str, size: int, dest: Path, chunks: int) -> None:
    hexdigest = digest.split(":", 1)[1]
    if dest.exists():
        if dest.stat().st_size == size and digest_of(dest) == hexdigest:
            say(f"cached  {digest[:23]} ({size / 1048576:.1f} MB)")
            return
        dest.unlink()

    say(f"start   {digest[:23]} ({size / 1048576:.1f} MB, {chunks} chunks)")
    url = f"{entry['registry']}/v2/{REPO}/blobs/{digest}"
    bounds = []
    span = size // chunks
    cursor = 0
    for index in range(chunks):
        end = size - 1 if index == chunks - 1 else cursor + span - 1
        bounds.append((index, cursor, end))
        cursor = end + 1

    parts = [dest.with_suffix(dest.suffix + f".part{index}") for index, _, _ in bounds]
    started = time.time()
    done = 0

    def worker(item):
        nonlocal done
        index, start, end = item
        target = parts[index]
        if target.exists() and target.stat().st_size == end - start + 1:
            done += 1
            return
        last = None
        for attempt in range(4):
            try:
                token = fetch_token(entry)
                curl_range(url, auth_headers(entry, token), start, end, target)
                done += 1
                elapsed = max(time.time() - started, 0.001)
                say(f"  chunk {done}/{chunks}  {done * span / 1048576 / elapsed:.2f} MB/s")
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"chunk {index} of {digest} failed: {last}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=chunks) as pool:
        list(pool.map(worker, bounds))

    with dest.open("wb") as out:
        for target in parts:
            with target.open("rb") as part:
                shutil.copyfileobj(part, out, 1 << 20)
    for target in parts:
        target.unlink()

    if dest.stat().st_size != size:
        raise RuntimeError(f"{dest} has {dest.stat().st_size} bytes, expected {size}")
    actual = digest_of(dest)
    if actual != hexdigest:
        raise RuntimeError(f"digest mismatch for {digest}: got sha256:{actual}")
    say(f"verified {digest[:23]} in {time.time() - started:.0f}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--chunks", type=int, default=14)
    parser.add_argument("--registry", default="daocloud")
    parser.add_argument("--skip-tar", action="store_true")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    blobs = out / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)

    entry = next((e for e in REGISTRIES if e["name"] == args.registry), REGISTRIES[0])
    say(f"registry: {entry['name']} ({entry['registry']})")

    token = fetch_token(entry)
    headers = auth_headers(entry, token)

    index = http_json(f"{entry['registry']}/v2/{REPO}/manifests/{REF}", {
        **headers,
        "Accept": "application/vnd.docker.distribution.manifest.list.v2+json,"
                  "application/vnd.oci.image.index.v1+json",
    })
    candidates = index.get("manifests") or [index]
    chosen = None
    for candidate in candidates:
        platform = candidate.get("platform") or {}
        if platform.get("os") == "windows" and platform.get("architecture") == "amd64":
            chosen = candidate
            break
    if chosen is None:
        raise RuntimeError("no windows/amd64 manifest in the index")

    say(f"manifest {chosen['digest'][:23]} (os.version {chosen['platform'].get('os.version')})")
    token = fetch_token(entry)
    manifest_bytes = http_bytes(
        f"{entry['registry']}/v2/{REPO}/manifests/{chosen['digest']}",
        auth_headers(entry, token),
    )
    manifest = json.loads(manifest_bytes)
    manifest_hex = hashlib.sha256(manifest_bytes).hexdigest()
    if f"sha256:{manifest_hex}" != chosen["digest"]:
        raise RuntimeError("manifest digest mismatch")
    (blobs / manifest_hex).write_bytes(manifest_bytes)

    token = fetch_token(entry)
    config_bytes = http_bytes(
        f"{entry['registry']}/v2/{REPO}/blobs/{manifest['config']['digest']}",
        auth_headers(entry, token),
    )
    config_hex = manifest["config"]["digest"].split(":", 1)[1]
    if hashlib.sha256(config_bytes).hexdigest() != config_hex:
        raise RuntimeError("config digest mismatch")
    (blobs / config_hex).write_bytes(config_bytes)

    total = sum(layer["size"] for layer in manifest["layers"])
    say(f"layers: {len(manifest['layers'])} totalling {total / 1048576:.1f} MB")

    for layer in manifest["layers"]:
        size = layer["size"]
        chunks = args.chunks if size > 200 * 1048576 else max(4, args.chunks // 2)
        download_blob(entry, layer["digest"], size, blobs / layer["digest"].split(":", 1)[1], chunks)

    (out / "oci-layout").write_text('{"imageLayoutVersion": "1.0.0"}', encoding="utf-8")
    index_doc = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "manifests": [
            {
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "digest": chosen["digest"],
                "size": len(manifest_bytes),
                "platform": PLATFORM,
                "annotations": {
                    "org.opencontainers.image.ref.name":
                        "mcr.microsoft.com/windows/servercore:ltsc2022",
                    "io.containerd.image.name":
                        "mcr.microsoft.com/windows/servercore:ltsc2022",
                },
            }
        ],
    }
    (out / "index.json").write_text(json.dumps(index_doc, indent=2), encoding="utf-8")

    archive = out / "servercore-ltsc2022-oci.tar"
    if not args.skip_tar:
        say(f"writing {archive.name}")
        with tarfile.open(archive, "w") as tar:
            tar.add(out / "oci-layout", arcname="oci-layout")
            tar.add(out / "index.json", arcname="index.json")
            for blob in sorted(blobs.iterdir()):
                tar.add(blob, arcname=f"blobs/sha256/{blob.name}")
        say(f"archive ready: {archive} ({archive.stat().st_size / 1048576:.0f} MB)")
    say("next: docker load -i " + str(archive))
    return 0


if __name__ == "__main__":
    sys.exit(main())
