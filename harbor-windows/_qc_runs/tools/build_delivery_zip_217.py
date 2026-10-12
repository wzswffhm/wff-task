"""Build the 217 delivery zip in the platform layout the user specified:

    <zip root>/
      outside_harbor/<task-id>.json                     # 平台导入 JSON
      outside_harbor-assets/<task-id>/
          task.toml / instruction.md / source.json
          environment/ solution/ tests/ verifier/
      jobs/<job-id>/{agent,verifier}                     # 与 assets 平级

217 has no platform_import.json and no <task-id>/verifier/ in the repo, so both
are produced here: the import JSON follows the 215 precedent, and verifier/ is
seeded with the official (oracle golden) verifier artefacts.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "wfflab__wreparse-217"
SRC = WS / "harbor-windows" / TASK
OUT_DIR = WS / "deliverables" / "2026-10-08_harbor-windows-整改" / "package"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ZIP = OUT_DIR / f"{TASK}-v1.1.0-delivery.zip"

GOLDEN_JOB = "20261008T200608-golden-oracle-01"

SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"}
SKIP_FILES = {".DS_Store"}


def tree_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(p for p in task_dir.rglob("*")
                   if p.is_file() and "jobs" not in p.relative_to(task_dir).parts)
    for path in files:
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


import tomllib
cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
import_json = {
    "instance_id": TASK,
    "task_version": cfg["task"]["version"],
    "task_hash": tree_hash(SRC),
    "docker_image": "outside-harbor/wfflab__wreparse-217:1.0",
    "image_digest": "sha256:37fdf8e192c68dcc7b88c6a529e49f13141fb8fbccbe8fbad908733f74db68f0",
    "instruction_file": f"{TASK}/instruction.md",
    "assets_path": TASK,
    "harness": "standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1（Harbor schema 1.3；Windows 容器 .bat 入口）",
    "tags": ["coding", "windows", "windows-bench"],
    "primary_direction": "文件系统与路径",
    "difficulty": cfg["metadata"]["difficulty"],
    "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以 outside_harbor-assets/"
              f"{TASK}/ 中通过冻结 Schema 校验的内容为准。两者引用同一身份三元组。"),
}

items: list[tuple[Path, str]] = []          # (source file, arcname)
entries_dirs: list[str] = []

for dirpath, dirnames, filenames in __import__("os").walk(SRC):
    current = Path(dirpath)
    rel = current.relative_to(SRC)
    parts = rel.parts
    if parts[:1] == ("jobs",):
        dirnames[:] = []
        continue
    dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
    for f in sorted(filenames):
        if f in SKIP_FILES or f.endswith(".pyc"):
            continue
        arc = f"outside_harbor-assets/{TASK}/{(rel / f).as_posix()}"
        items.append((current / f, arc))

# official verifier artefacts (oracle golden run) -> <task-id>/verifier/
gdir = SRC / "jobs" / GOLDEN_JOB / "verifier"
for f in sorted(gdir.iterdir()) if gdir.is_dir() else []:
    if f.is_file():
        items.append((f, f"outside_harbor-assets/{TASK}/verifier/{f.name}"))

# jobs/ at zip root
for f in sorted((SRC / "jobs").rglob("*")):
    if f.is_file():
        items.append((f, f"jobs/{f.relative_to(SRC / 'jobs').as_posix()}"))

entries_dirs.append(f"outside_harbor-assets/{TASK}/verifier/")

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("outside_harbor/" + TASK + ".json",
                json.dumps(import_json, ensure_ascii=False, indent=2) + "\n")
    for path, arc in items:
        zf.write(path, arc)

names = zipfile.ZipFile(ZIP).namelist()
tops = sorted({n.split("/")[0] for n in names})
print(f"zip      : {ZIP.name}  {ZIP.stat().st_size} B  条目 {len(names)}")
print(f"顶层     : {tops}")
print(f"outside_harbor/          : {sum(1 for n in names if n.startswith('outside_harbor/'))}")
print(f"outside_harbor-assets/   : {sum(1 for n in names if n.startswith('outside_harbor-assets/'))}")
print(f"jobs/ (顶层)             : {sum(1 for n in names if n.startswith('jobs/'))}")
print(f"{TASK}/verifier/ 内      : {sum(1 for n in names if f'assets/{TASK}/verifier/' in n)}")
print("verifier/ 内容:", sorted(n.split('/')[-1] for n in names if f'assets/{TASK}/verifier/' in n))
print(f"sha256   : {hashlib.sha256(ZIP.read_bytes()).hexdigest()}")


