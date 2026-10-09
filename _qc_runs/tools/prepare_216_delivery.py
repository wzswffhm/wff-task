"""wfflab__wchunk-216 交付打包（口径与 215/217 完全一致）。

  1. 重写 platform_import.json（身份三元组 + tree_hash，排除 jobs/ 与自身）
  2. 生成两个 ZIP：
       <task>-v<ver>-delivery.zip   # 平台布局：outside_harbor/ + outside_harbor-assets/ + jobs/
       <task>-v<ver>.zip            # 题包布局：<task>/**（含 jobs/），走 package_task_zip.py 口径
  3. 打印 sha256 与门禁读数，供 README/checksums 引用

前置：jobs/ 已由 build_jobs.py（汇总）+ produce_jobs.py（Harbor 6 轮）生成。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
import zipfile
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "wfflab__wchunk-216"
SRC = WS / "harbor-windows" / TASK
SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"}
SKIP_FILES = {".DS_Store"}


def tree_hash(task_dir: Path) -> str:
    """题包定义树哈希：排除 jobs/ 与 platform_import.json（否则无法自洽）。"""
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file()
        and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_asset_files() -> list[tuple[Path, str]]:
    """题包本体（不含 jobs/）→ outside_harbor-assets/<task>/..."""
    items: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(SRC):
        current = Path(dirpath)
        rel = current.relative_to(SRC)
        if rel.parts[:1] == ("jobs",):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            items.append((current / f, f"outside_harbor-assets/{TASK}/{(rel / f).as_posix()}"))
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, help="交付输出目录（package/ 会自动创建）")
    ap.add_argument("--image-digest", default=None, help="sha256:<digest>，缺省写 PENDING_BUILD")
    ap.add_argument("--primary-direction", required=True)
    ap.add_argument("--harness", default="standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1"
                                        "（Harbor schema 1.3；Windows 容器 .bat 入口）")
    args = ap.parse_args()

    cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
    if not (SRC / "jobs").is_dir():
        raise SystemExit("题包缺 jobs/：先跑 build_jobs.py 与 produce_jobs.py")

    task_version = cfg["task"]["version"]
    digest = tree_hash(SRC)
    import_json = {
        "instance_id": TASK,
        "task_version": task_version,
        "task_hash": digest,
        "docker_image": f"outside-harbor/{TASK}:1.0",
        "image_digest": args.image_digest or "PENDING_BUILD",
        "instruction_file": f"{TASK}/instruction.md",
        "assets_path": TASK,
        "harness": args.harness,
        "tags": ["coding", "windows", "windows-bench"],
        "primary_direction": args.primary_direction,
        "difficulty": cfg["metadata"]["difficulty"],
        "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以同目录（"
                  f"{TASK}/）中通过冻结 Schema 校验的内容为准。两者引用同一身份三元组。"),
    }
    (SRC / "platform_import.json").write_text(
        json.dumps(import_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"platform_import.json  task_version={task_version}  task_hash={digest}")

    out_dir = Path(args.out_dir).resolve() / "package"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1) 平台布局 delivery.zip -------------------------------------
    delivery = out_dir / f"{TASK}-v{task_version}-delivery.zip"
    items = collect_asset_files()
    golden = sorted((SRC / "jobs").glob("*-golden-oracle-01"))
    if golden:
        gdir = golden[0] / "verifier"
        for f in sorted(gdir.iterdir()) if gdir.is_dir() else []:
            if f.is_file():
                items.append((f, f"outside_harbor-assets/{TASK}/verifier/{f.name}"))
    job_files = [p for p in sorted((SRC / "jobs").rglob("*")) if p.is_file()]

    with zipfile.ZipFile(delivery, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"outside_harbor/{TASK}.json",
                    json.dumps(import_json, ensure_ascii=False, indent=2) + "\n")
        for path, arc in items:
            zf.write(path, arc)
        for p in job_files:
            zf.write(p, f"jobs/{p.relative_to(SRC / 'jobs').as_posix()}")

    names = zipfile.ZipFile(delivery).namelist()
    print(f"\ndelivery zip : {delivery.name}  {delivery.stat().st_size} B  条目 {len(names)}")
    print(f"  顶层        : {sorted({n.split('/')[0] for n in names})}")
    print(f"  assets 条目 : {sum(1 for n in names if n.startswith(f'outside_harbor-assets/{TASK}/'))}")
    print(f"  jobs 条目   : {sum(1 for n in names if n.startswith('jobs/'))}")
    print(f"  verifier/   : {sorted(n.split('/')[-1] for n in names if f'assets/{TASK}/verifier/' in n)}")
    print(f"  extras 泄漏 : {any('/extras/' in n for n in names)}")
    print(f"  sha256      : {sha256_of(delivery)}")

    # ---- 2) 题包布局 <task>-v<ver>.zip --------------------------------
    pkg = out_dir / f"{TASK}-v{task_version}.zip"
    pkg_items: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(SRC):
        current = Path(dirpath)
        rel = current.relative_to(SRC)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for f in sorted(filenames):
            if f in SKIP_FILES or f.endswith(".pyc"):
                continue
            pkg_items.append((current / f, f"{TASK}/{(rel / f).as_posix()}"))
    with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arc in pkg_items:
            zf.write(path, arc)

    pnames = zipfile.ZipFile(pkg).namelist()
    required = ["source.json", "solution/README.md", "tests/required_testcases.json"]
    missing = [f"{TASK}/{r}" for r in required if f"{TASK}/{r}" not in pnames]
    if not any(f"{TASK}/solution/{s}" in pnames for s in ("solve.ps1", "solve.bat")):
        missing.append(f"{TASK}/solution/solve.ps1|solve.bat")
    if missing:
        print("!! 题包 ZIP 缺甲方 QC 必备件，拒绝交付：")
        for m in missing:
            print(f"   - {m}")
        return 2
    leaked = [n for n in pnames if "/extras/" in n or "/__pycache__/" in n or n.endswith(".pyc")]
    if leaked:
        print("!! 题包 ZIP 含禁入内容：", leaked)
        return 2
    print(f"\npackage zip  : {pkg.name}  {pkg.stat().st_size} B  条目 {len(pnames)}")
    print(f"  sha256      : {sha256_of(pkg)}")

    # ---- 3) 门禁读数 --------------------------------------------------
    idx = SRC / "jobs" / "_index" / "qualification_summary.json"
    if idx.is_file():
        q = json.loads(idx.read_text(encoding="utf-8-sig"))
        print("\n资格门禁：")
        print(f"  qualified = {q.get('qualified')}")
        print(f"  reasons   = {q.get('reasons')}")
        print(f"  epoch     = {q.get('qualification_epoch')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
