#!/usr/bin/env python3
"""hash_package.py —— 计算并回写 harbor-windows 题包的身份哈希与目录校验和

## 职责

1. 计算身份三元组里的 `task_hash`：
       sha256("task_id=…\\ntask_version=…\\ninstruction_md_sha256=…\\n"
              "test_patch_sha256=…\\noracle_patch_sha256=…\\ndockerfile_sha256=…")
   **末行不带换行**（这是冻结口径，改动会让所有历史哈希失效）。
2. 把 `task_hash` / `task_version` / `docker_image` 回写到四处身份文件：
   `task.toml`、`tests/swelive_spec.json`、`platform_import.json`、
   `extras/metadata/manifest.json`，并把各制品 sha256 写进 manifest.artifacts。
3. 重新生成 `_index/checksums.sha256`（覆盖整个题包类型目录）。

## 用法

    # 只打印将要写入的内容，不改文件（默认）
    python hash_package.py --package ../../harbor-windows

    # 只处理某一题
    python hash_package.py --package ../../harbor-windows --task wfflab__wsync-142

    # 实际写入
    python hash_package.py --package ../../harbor-windows --write

## checksums 收录范围

收录 `harbor-windows/` 下所有文件，**排除**：
  - `_index/checksums.sha256`（自身）
  - 任意 `__pycache__/` 与 `*.pyc`
  - `<task>/extras/model_runs/_judge/`（本机 L2 判分沙箱，内含环境副本，可随时重建）

> 注意：`task_hash` 刻意**不含** `task.toml` 自身，否则无法把哈希写回去；
> 但 `task.toml` 的 sha256 会作为制品哈希记进 `manifest.artifacts.task_toml_sha256`。
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

SKIP_DIRS = {"__pycache__", ".git"}
SKIP_REL_PREFIXES = ("_index/checksums.sha256",)
SKIP_REL_PARTS = ("extras/model_runs/_judge",)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def compute_task_hash(task_id: str, version: str, artifacts: dict) -> str:
    material = (
        "task_id=" + task_id + "\n"
        + "task_version=" + version + "\n"
        + "instruction_md_sha256=" + artifacts["instruction_md_sha256"] + "\n"
        + "test_patch_sha256=" + artifacts["test_patch_sha256"] + "\n"
        + "oracle_patch_sha256=" + artifacts["oracle_patch_sha256"] + "\n"
        + "dockerfile_sha256=" + artifacts["dockerfile_sha256"]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def task_artifact_paths(task_dir: str) -> dict:
    return {
        "instruction_md_sha256": os.path.join(task_dir, "instruction.md"),
        "test_patch_sha256": os.path.join(task_dir, "tests", "test_patch.diff"),
        "oracle_patch_sha256": os.path.join(task_dir, "solution", "oracle.patch"),
        "dockerfile_sha256": os.path.join(task_dir, "environment", "Dockerfile"),
        "spec_sha256": os.path.join(task_dir, "tests", "swelive_spec.json"),
        "grade_py_sha256": os.path.join(task_dir, "tests", "grade.py"),
        "test_ps1_sha256": os.path.join(task_dir, "tests", "test.ps1"),
        "task_toml_sha256": os.path.join(task_dir, "task.toml"),
    }


def sync_task(pkg: str, tid: str, write: bool, log) -> str:
    task_dir = os.path.join(pkg, tid)
    spec_p = os.path.join(task_dir, "tests", "swelive_spec.json")
    pi_p = os.path.join(task_dir, "platform_import.json")
    mn_p = os.path.join(task_dir, "extras", "metadata", "manifest.json")
    tt_p = os.path.join(task_dir, "task.toml")

    for p in (spec_p, pi_p, mn_p, tt_p):
        if not os.path.isfile(p):
            raise SystemExit("缺少身份文件：%s" % p)

    spec = read_json(spec_p)
    version = str(spec.get("task_version") or "").strip()
    if not version:
        raise SystemExit("%s: swelive_spec.json 缺少 task_version" % tid)

    paths = task_artifact_paths(task_dir)
    for key in ("instruction_md_sha256", "test_patch_sha256",
                "oracle_patch_sha256", "dockerfile_sha256"):
        if not os.path.isfile(paths[key]):
            raise SystemExit("%s: 缺少制品 %s" % (tid, paths[key]))
    art = {k: sha256_file(p) for k, p in paths.items()}

    task_hash = compute_task_hash(tid, version, art)
    image_ref = spec.get("image_ref") or ""

    # ---------------- swelive_spec.json ----------------
    if spec.get("task_hash") != task_hash:
        log("  spec.task_hash  %s -> %s" % (str(spec.get("task_hash"))[:12], task_hash[:12]))
        spec["task_hash"] = task_hash
        if write:
            write_json(spec_p, spec)

    # ---------------- platform_import.json ----------------
    pi = read_json(pi_p)
    changed = False
    for key, val in (("instance_id", None), ("task_version", version),
                     ("task_hash", task_hash), ("docker_image", image_ref)):
        if key == "instance_id":
            continue
        if val is not None and pi.get(key) != val:
            log("  platform_import.%s  %r -> %r" % (key, pi.get(key), val))
            pi[key] = val
            changed = True
    if changed and write:
        write_json(pi_p, pi)

    # ---------------- task.toml ----------------
    tt = open(tt_p, encoding="utf-8", errors="replace").read()
    orig_tt = tt
    tt = re.sub(r'(?m)^version\s*=\s*"[^"]*"', 'version = "%s"' % version, tt, count=1)
    tt = re.sub(r'task_hash(\s*=\s*)[0-9a-f]{64}', r'task_hash\g<1>' + task_hash, tt)
    if image_ref:
        tt = re.sub(r'(?m)^docker_image\s*=\s*"[^"]*"',
                    'docker_image = "%s"' % image_ref, tt, count=1)
    if tt != orig_tt:
        log("  task.toml 已更新（version / task_hash / docker_image）")
        if write:
            open(tt_p, "w", encoding="utf-8", newline="\n").write(tt)

    # ---------------- manifest.json（task.toml / spec 已定稿后再取哈希） ----------------
    art_after = {k: sha256_file(p) for k, p in paths.items()}
    mn = read_json(mn_p)
    mn["task_id"] = tid
    mn["task_version"] = version
    mn["task_hash"] = task_hash
    if image_ref:
        mn["image_ref"] = image_ref
    mn["artifacts"] = {
        "task_toml_sha256": art_after["task_toml_sha256"],
        "instruction_md_sha256": art_after["instruction_md_sha256"],
        "test_patch_sha256": art_after["test_patch_sha256"],
        "oracle_patch_sha256": art_after["oracle_patch_sha256"],
        "spec_sha256": art_after["spec_sha256"],
        "dockerfile_sha256": art_after["dockerfile_sha256"],
        "grade_py_sha256": art_after["grade_py_sha256"],
        "test_ps1_sha256": art_after["test_ps1_sha256"],
    }
    if write:
        write_json(mn_p, mn)
    log("  manifest.artifacts 已同步（task_toml / spec 取更新后哈希）")

    log("  task_hash = %s" % task_hash)
    return task_hash


def regen_checksums(pkg: str, write: bool, log) -> int:
    entries = []
    for dirpath, dirnames, filenames in os.walk(pkg):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, pkg).replace("\\", "/")
            if rel.startswith(SKIP_REL_PREFIXES):
                continue
            if any(part in rel for part in SKIP_REL_PARTS):
                continue
            entries.append((rel, sha256_file(full)))
    entries.sort()
    body = "".join("%s  %s\n" % (h, rel) for rel, h in entries)
    out = os.path.join(pkg, "_index", "checksums.sha256")
    if write:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8", newline="\n").write(body)
    log("  checksums.sha256 收录 %d 个文件" % len(entries))
    return len(entries)


def main():
    ap = argparse.ArgumentParser(description="harbor-windows 身份哈希与校验和")
    ap.add_argument("--package", required=True, help="harbor-windows 题包类型目录")
    ap.add_argument("--task", help="只处理指定 task_id")
    ap.add_argument("--write", action="store_true", help="实际写入（默认只预览）")
    a = ap.parse_args()

    pkg = os.path.abspath(a.package)
    tids = [a.task] if a.task else sorted(
        d for d in os.listdir(pkg)
        if os.path.isfile(os.path.join(pkg, d, "task.toml"))
    )
    if not tids:
        raise SystemExit("未找到题包")

    print("=" * 66)
    print("hash_package —— %s（%s）" % (pkg, "写入" if a.write else "预览，未改动任何文件"))
    print("=" * 66)
    for tid in tids:
        print("[%s]" % tid)
        sync_task(pkg, tid, a.write, lambda s: print(s))
    print("[_index]")
    regen_checksums(pkg, a.write, lambda s: print(s))
    print("生成时间：%s" % datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"))
    if not a.write:
        print("（预览模式：加 --write 才会落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
