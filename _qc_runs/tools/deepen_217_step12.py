"""217 加深（第十二步·收尾）：同步 source.json，重算 task_hash，重出 zip 与 checksums。

顺序敏感：source.json 在题包内，改它会改变 task_hash，所以必须
  source.json -> tree_hash -> tasks_index.csv / CHANGELOG -> zip -> checksums.sha256
依次完成，任一环节失败即中止，避免索引与实物脱节。

同时把 results/（运行时产物，非题包内容）排除出交付 zip——旧交付包同样不含它。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
ROOT = WS / "harbor-windows"
INDEX = ROOT / "_index"
TASK_ID = "wfflab__wreparse-217"
SRC = ROOT / TASK_ID
VERSION = "1.2.0"
TODAY = "2026-10-09"
CST = timezone(timedelta(hours=8))

SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache", "results"}
SKIP_FILES = {".DS_Store"}
failed = False


def tree_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        rel = path.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8") + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


# ------------------------------------------------------------------ 1. source.json
path = SRC / "source.json"
doc = json.loads(path.read_text(encoding="utf-8-sig"))
if doc.get("task_version") != VERSION:
    doc["task_version"] = VERSION
if doc.get("source_time") != TODAY:
    doc["source_time"] = TODAY
lineage = doc.get("lineage", "")
if "deepened to L4" not in lineage:
    doc["lineage"] = (lineage + " -> L4 deepening round (task_version 1.2.0): "
                      "provider-layer authoritative facts, visible smoke test, "
                      "6 additional contract checks").strip(" ->")
path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"ok source.json: task_version={doc['task_version']} source_time={doc['source_time']}")

# ------------------------------------------------------------------ 2. task_hash
new_hash = tree_hash(SRC)
print(f"ok task_hash = {new_hash}")

# ------------------------------------------------------- 3. tasks_index.csv hash
path = INDEX / "tasks_index.csv"
raw = path.read_text(encoding="utf-8-sig")
rows = list(csv.reader(io.StringIO(raw)))
header = rows[0]
out_rows = [header]
hit = 0
for row in rows[1:]:
    if not row:
        continue
    rec = dict(zip(header, row))
    if rec.get("task_id") == TASK_ID:
        rec["task_hash"] = new_hash
        rec["task_version"] = VERSION
        hit += 1
    out_rows.append([rec.get(h, "") for h in header])
buf = io.StringIO()
csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_ALL).writerows(out_rows)
path.write_text(buf.getvalue(), encoding="utf-8")
print(f"ok tasks_index.csv: 更新 {hit} 行 hash")
if hit != 1:
    failed = True

# --------------------------------------------------------- 4. CHANGELOG 里的 hash
path = INDEX / "CHANGELOG.md"
text = path.read_text(encoding="utf-8")
new_text, n = re.subn(r"(本机控制组复验通过[^\n]*\n(?:.*\n)*?- \*\*包哈希\*\*：`task_hash = )[0-9a-f]{64}",
                      lambda m: m.group(1) + new_hash, text)
if n:
    path.write_text(new_text, encoding="utf-8")
    print(f"ok CHANGELOG.md: 更新 hash（{n} 处）")
else:
    # 换一种更宽松的替换：直接替换文档里出现的旧 217 hash
    old = "480d7702632ebb1c1974156c4f0a821e39ec082832dc8b3ea290b41c6956b761"
    if old in text:
        path.write_text(text.replace(old, new_hash), encoding="utf-8")
        print("ok CHANGELOG.md: 替换旧 hash")
    else:
        print("!! CHANGELOG.md: 未找到 217 的 hash，跳过")

# ------------------------------------------------------------------ 5. 重新打包
import tomllib
cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
import_json = {
    "instance_id": TASK_ID,
    "task_version": cfg["task"]["version"],
    "task_hash": new_hash,
    "docker_image": "outside-harbor/wfflab__wreparse-217:1.0",
    "image_digest": "sha256:37fdf8e192c68dcc7b88c6a529e49f13141fb8fbccbe8fbad908733f74db68f0",
    "instruction_file": f"{TASK_ID}/instruction.md",
    "assets_path": TASK_ID,
    "harness": ("standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1"
                "（Harbor schema 1.3；Windows 容器 .bat 入口）"),
    "tags": ["coding", "windows", "windows-bench"],
    "primary_direction": "文件系统与路径",
    "difficulty": cfg["metadata"]["difficulty"],
    "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以 "
              f"outside_harbor-assets/{TASK_ID}/ 中通过冻结 Schema 校验的内容为准。"
              "两者引用同一身份三元组。"),
}

out_dir = WS / "deliverables" / "2026-10-09_wreparse217-加深L4" / "package"
out_dir.mkdir(parents=True, exist_ok=True)
zip_path = out_dir / f"{TASK_ID}-v{VERSION}-delivery.zip"

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
        items.append((current / f, f"outside_harbor-assets/{TASK_ID}/{(rel / f).as_posix()}"))

oracle_dirs = sorted(p for p in (SRC / "jobs").glob("*-golden-oracle-01") if (p / "verifier").is_dir())
if oracle_dirs:
    gdir = oracle_dirs[-1] / "verifier"
    for f in sorted(gdir.iterdir()):
        if f.is_file():
            items.append((f, f"outside_harbor-assets/{TASK_ID}/verifier/{f.name}"))
    print(f"ok verifier 来源: {oracle_dirs[-1].name}")

for f in sorted((SRC / "jobs").rglob("*")):
    if f.is_file():
        items.append((f, f"jobs/{f.relative_to(SRC / 'jobs').as_posix()}"))

if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"outside_harbor/{TASK_ID}.json",
                json.dumps(import_json, ensure_ascii=False, indent=2) + "\n")
    for path_, arc in items:
        zf.write(path_, arc)

names = zipfile.ZipFile(zip_path).namelist()
leaked = [n for n in names if f"assets/{TASK_ID}/results/" in n]
print(f"ok zip: {zip_path.name}  {zip_path.stat().st_size} B  条目 {len(names)}  results 泄漏 {len(leaked)}")
if leaked:
    print(f"!! zip 仍含 results/: {leaked}")
    failed = True
zip_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()

# ------------------------------------------------- 6. 重新生成 checksums.sha256
path = INDEX / "checksums.sha256"
lines = [
    f"# harbor-windows checksums (scope: 2 packages, generated {TODAY})",
    "# algorithm: sha256 of each file, sorted by forward-slash relative path",
    "# task_hash rule: sha256 over the task definition tree: for every file under the task root "
    "except jobs/ and platform_import.json (the latter records this value, so it is excluded to keep "
    "the hash self-consistent), in sorted forward-slash relative-path order, feed '<relpath>\\n<sha256(file)>\\n'",
]
entries: list[tuple[str, str]] = []
for p in sorted(ROOT.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(ROOT).as_posix()
    if "__pycache__" in rel or rel.endswith(".pyc"):
        continue
    # 跳过 _index 自身的 checksums 文件，避免自指
    if rel == "_index/checksums.sha256":
        continue
    entries.append((rel, hashlib.sha256(p.read_bytes()).hexdigest()))
for rel, h in sorted(entries):
    lines.append(f"{h}  {rel}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"ok checksums.sha256: {len(entries)} 条")
print(f"   zip sha256 = {zip_sha}")

print()
print("RESULT:", "部分失败" if failed else "第十二步完成（收尾同步）")
sys.exit(1 if failed else 0)
