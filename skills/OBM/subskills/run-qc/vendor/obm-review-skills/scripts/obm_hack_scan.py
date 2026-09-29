#!/usr/bin/env python3
"""Collect source/benchmark content matches. Candidates require human/Agent classification."""
from __future__ import annotations

import argparse
import bz2
from collections import defaultdict, Counter
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile

from review_common import (MAX_FILE, canonical, digest, meaningful_issues,
                           read_bytes, walk_files, write_json)

ARCHIVES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")
UNSUPPORTED = (".7z", ".rar", ".zst")


def features(raw):
    """Return content signatures, never domain/capability scores."""
    normalized = raw
    records = set()
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        return digest(normalized), records, None
    normalized = text.encode()
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        normalized = canonical(value)
        arrays = [value] if isinstance(value, list) else (
            [v for v in value.values() if isinstance(v, list)] if isinstance(value, dict) else [])
        for array in arrays:
            for item in array:
                encoded = canonical(item)
                if len(encoded) >= 24:
                    records.add(digest(encoded))
    except (ValueError, TypeError):
        pass
    # Exact nontrivial lines catch partial copied code/CSV/JSONL; 12-token shingles
    # catch reflowed prose/code. These are candidate signals, not proof.
    for line in text.splitlines():
        line = " ".join(line.split())
        if len(line) >= 32:
            records.add(digest(line.encode()))
    tokens = re.findall(r"\w+|[^\w\s]", text)
    for i in range(0, max(0, len(tokens) - 11)):
        shingle = " ".join(tokens[i:i + 12])
        if len(shingle) >= 48:
            records.add(digest(shingle.encode()))
    return digest(normalized), records, text


def collect(root, max_file=MAX_FILE, max_total=256 * MAX_FILE, max_files=50000,
            match_chunks=None):
    """Read bounded files and archive members in memory; no archive extraction."""
    files, issues = [], []
    budget = {"bytes": 0, "entries": 0}

    def add(path, raw, depth=0, container=None):
        budget["bytes"] += len(raw)
        budget["entries"] += 1
        if budget["bytes"] > max_total or budget["entries"] > max_files:
            raise ValueError("collection_budget_exceeded")
        norm, chunks, text = features(raw)
        item = {"path": path, "sha256": digest(raw), "normalized_sha256": norm,
                "bytes": len(raw), "container": container, "excerpt": (text or "")[:700],
                "_unit_count": len(chunks),
                "_chunks": chunks if match_chunks is None else chunks & match_chunks,
                "_text": text[:4096] if text is not None else None}
        files.append(item)
        lower = path.lower()
        is_zip = raw.startswith((b"PK\x03\x04", b"PK\x05\x06")) or lower.endswith((".zip", ".whl", ".jar"))
        is_tar = raw[257:262] == b"ustar" or lower.endswith(ARCHIVES[1:])
        codec = (gzip.GzipFile if raw.startswith(b"\x1f\x8b") else
                 bz2.BZ2File if raw.startswith(b"BZh") else
                 lzma.LZMAFile if raw.startswith(b"\xfd7zXZ\x00") else None)
        if is_zip or is_tar or codec:
            if depth >= 2:
                issues.append({"path": path, "reason": "archive_depth_limit"})
                return
            try:
                if is_zip:
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        for member in archive.infolist():
                            if member.is_dir():
                                continue
                            name = member.filename
                            mode = member.external_attr >> 16
                            if member.flag_bits & 1 or mode & 0o170000 == 0o120000:
                                issues.append({"path": path + "!/" + name,
                                               "reason": "encrypted_or_symlink_member"})
                                continue
                            if not safe_member(name, member.file_size, path):
                                continue
                            with archive.open(member) as stream:
                                content = stream.read(max_file + 1)
                            if len(content) > max_file:
                                raise ValueError("archive_member_byte_limit")
                            add(path + "!/" + name, content, depth + 1,
                                {"path": path, "sha256": item["sha256"]})
                elif is_tar:
                    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
                        for member in archive:
                            if member.isdir():
                                continue
                            if not member.isfile():
                                issues.append({"path": path + "!/" + member.name,
                                               "reason": "non_regular_archive_member"})
                                continue
                            if not safe_member(member.name, member.size, path):
                                continue
                            content = archive.extractfile(member).read(max_file + 1)
                            add(path + "!/" + member.name, content, depth + 1,
                                {"path": path, "sha256": item["sha256"]})
                else:
                    stream = (gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb")
                              if codec is gzip.GzipFile else codec(io.BytesIO(raw), mode="rb"))
                    with stream:
                        content = stream.read(max_file + 1)
                    if len(content) > max_file:
                        raise ValueError("decompressed byte limit %d" % max_file)
                    add(path + "!/decompressed", content, depth + 1,
                        {"path": path, "sha256": item["sha256"]})
            except (OSError, EOFError, ValueError, RuntimeError, zipfile.BadZipFile,
                    tarfile.TarError, lzma.LZMAError) as error:
                issues.append({"path": path, "reason": str(error)})
        elif lower.endswith(UNSUPPORTED) or raw.startswith((b"7z\xbc\xaf\x27\x1c", b"Rar!", b"\x28\xb5\x2f\xfd")):
            issues.append({"path": path, "reason": "unsupported_compression"})

    def safe_member(name, size, parent):
        budget["entries"] += 1
        if budget["entries"] > max_files or budget["bytes"] + size > max_total:
            raise ValueError("collection_budget_exceeded")
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or size > max_file:
            issues.append({"path": parent + "!/" + name, "reason": "unsafe_or_large_member"})
            return False
        return True

    for path in walk_files(root, issues):
        if budget["bytes"] > max_total or budget["entries"] > max_files:
            issues.append({"path": str(root), "reason": "remaining_tree_not_scanned"})
            break
        try:
            if path.stat().st_size > max_file:
                if budget["bytes"] + path.stat().st_size > max_total:
                    raise ValueError("collection_budget_exceeded")
                hashed = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        size += len(block)
                        if budget["bytes"] + size > max_total:
                            raise ValueError("collection_budget_exceeded")
                        hashed.update(block)
                budget["bytes"] += size
                budget["entries"] += 1
                files.append({"path": str(path.absolute()), "sha256": hashed.hexdigest(),
                              "normalized_sha256": hashed.hexdigest(), "bytes": size,
                              "container": None, "excerpt": "", "_chunks": set(),
                              "_unit_count": 0, "_text": None, "scan_mode": "exact_hash_only"})
                issues.append({"path": str(path), "reason":
                               "byte limit %d: exact hash only; partial/archive content unscanned" % max_file})
            else:
                add(str(path.absolute()), read_bytes(path, max_file))
        except (OSError, ValueError, RecursionError) as error:
            issues.append({"path": str(path), "reason": str(error)})
    if not any(item["bytes"] for item in files):
        issues.append({"path": str(root), "reason": "no_readable_content"})
    return {"root": str(Path(root).absolute()), "files": files, "issues": issues,
            "bytes_read": budget["bytes"]}


def public_file(item):
    return {k: v for k, v in item.items() if not k.startswith("_")}


def compare(source, corpora, max_candidates=5000):
    raw_index, norm_index, chunk_index = defaultdict(list), defaultdict(list), defaultdict(set)
    benchmark_files = []
    for corpus in corpora:
        for item in corpus["files"]:
            idx = len(benchmark_files)
            benchmark_files.append(item)
            raw_index[item["sha256"]].append(idx)
            norm_index[item["normalized_sha256"]].append(idx)
            for chunk in item["_chunks"]:
                chunk_index[chunk].add(idx)
    candidates = []
    truncated = False
    for src in source["files"]:
        matches = {}
        for idx in raw_index[src["sha256"]]:
            matches[idx] = ("exact_bytes", None)
        for idx in norm_index[src["normalized_sha256"]]:
            matches.setdefault(idx, ("normalized_content", None))
        counts = Counter(idx for chunk in src["_chunks"] for idx in chunk_index.get(chunk, ()))
        for idx, overlap in counts.items():
            denom = min(src["_unit_count"], benchmark_files[idx]["_unit_count"])
            ratio = overlap / denom if denom else 0
            if overlap >= 3 and (ratio >= 0.2 or overlap >= 20):
                matches.setdefault(idx, ("partial_content", {"shared_units": overlap,
                                                             "smaller_file_fraction": round(ratio, 4)}))
        for idx, (method, overlap) in sorted(matches.items()):
            if len(candidates) >= max_candidates:
                truncated = True
                break
            other = benchmark_files[idx]
            item = {"method": method, "source": public_file(src),
                    "benchmark": public_file(other), "overlap": overlap}
            if src["_text"] is not None and other["_text"] is not None:
                a = set(src["_text"].splitlines())
                item["shared_line_examples"] = [line for line in other["_text"].splitlines()
                                                if line in a and len(line.strip()) >= 24][:5]
            item["candidate_id"] = digest(canonical(item))
            candidates.append(item)
        if truncated:
            break
    issues = list(source["issues"])
    for corpus in corpora:
        issues.extend(corpus["issues"])
    if not benchmark_files:
        issues.append({"path": "benchmark", "reason": "no_benchmark_content"})
    if truncated:
        issues.append({"path": "matches", "reason": "candidate_limit"})
    return {
        "schema_version": 2, "status": "CANDIDATES" if candidates else "NO_CANDIDATE_IN_SCOPE",
        "decision": "REQUIRES_ANALYST",
        "coverage_complete": not meaningful_issues(issues),
        "limits": {"method": "exact bytes / normalized JSON+newlines / exact chunks",
                   "limitations": "Does not prove absence of rewritten, encoded or semantic copying"},
        "source": {"root": source["root"], "files": [public_file(f) for f in source["files"]]},
        "benchmark_scope": [{"root": c["root"], "file_count": len(c["files"]),
                             "files": [public_file(f) for f in c["files"]]} for c in corpora],
        "issues": issues, "candidates": candidates}


def scan(source_root, benchmark_roots, **limits):
    source = collect(source_root, **limits)
    chunks = set().union(*(f["_chunks"] for f in source["files"]))
    return compare(source, [collect(p, match_chunks=chunks, **limits) for p in benchmark_roots])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--benchmark-root", action="append", required=True)
    parser.add_argument("--max-file-bytes", type=int, default=MAX_FILE)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = scan(args.sources, args.benchmark_root, max_file=args.max_file_bytes)
    write_json(args.output, report)
    print("candidates=%d complete=%s" % (len(report["candidates"]), report["coverage_complete"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
