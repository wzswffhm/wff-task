#!/usr/bin/env python3
"""Shared, bounded evidence IO. No proposal or benchmark code is executed."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

EXCLUDED = {".git", "__pycache__", ".pytest_cache", ".DS_Store"}
MAX_FILE = 8 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(value):
    return digest(canonical({k: v for k, v in value.items() if k != "packet_id"}))


def load_json(path):
    def reject(value):
        raise ValueError("non-finite JSON number: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n", encoding="utf-8")


def read_bytes(path, limit=MAX_FILE):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink not followed")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("file exceeds byte limit %d" % limit)
    return raw


def snapshot(path, text=True, limit=MAX_FILE):
    raw = read_bytes(path, limit)
    result = {"path": str(Path(path).absolute()), "sha256": digest(raw), "bytes": len(raw)}
    if text:
        result["text"] = raw.decode("utf-8-sig")
    return result


def walk_files(root, issues):
    """Report skipped paths; do not follow directory symlinks or hide vendor assets."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        issues.append({"path": str(root), "reason": "missing_directory_or_symlink"})
        return
    def onerror(error):
        issues.append({"path": str(error.filename), "reason": str(error)})
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=onerror):
        for name in list(dirs):
            path = Path(directory) / name
            if name in EXCLUDED or path.is_symlink():
                dirs.remove(name)
                issues.append({"path": str(path), "reason":
                               "excluded_metadata" if name in EXCLUDED else "symlink"})
        for name in sorted(names):
            path = Path(directory) / name
            if name in EXCLUDED:
                continue
            if path.is_symlink():
                issues.append({"path": str(path), "reason": "symlink"})
            else:
                yield path


def run(args, timeout=30, max_bytes=MAX_FILE, cwd=None):
    """Bound subprocess time and captured disk output; never invoke a shell."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(args, cwd=cwd, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL)
        deadline = time.monotonic() + timeout
        failure = None
        while proc.poll() is None:
            if time.monotonic() > deadline:
                failure = "command timeout"
                break
            if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > max_bytes:
                failure = "command output limit"
                break
            time.sleep(0.02)
        if failure:
            proc.kill()
        proc.wait()
        out.seek(0)
        err.seek(0)
        raw, error = out.read(max_bytes + 1), err.read(4096)
        if failure or len(raw) > max_bytes:
            raise ValueError(failure or "command output limit")
        if proc.returncode:
            # Avoid echoing command arguments (URLs may contain credentials).
            raise ValueError("command exit %d: %s" %
                             (proc.returncode, error.decode("utf-8", "replace")[:1000]))
        return raw


def meaningful_issues(issues):
    return [item for item in issues if item["reason"] != "excluded_metadata"]


if __name__ == "__main__":
    print("review_common: stdlib evidence IO ready")
