"""Verify that harbor-windows directory materials now match the two packages on disk."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
INDEX = ROOT / "_index"
TASKS = ["wfflab__wfmt-215", "wfflab__wreparse-217"]
problems: list[str] = []


def tree_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(p for p in task_dir.rglob("*")
                   if p.is_file() and "jobs" not in p.relative_to(task_dir).parts)
    for path in files:
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# 1) checksums.sha256 must match the tree it claims to cover
entries = {}
for line in (INDEX / "checksums.sha256").read_text(encoding="utf-8").splitlines():
    if line.startswith("#") or not line.strip():
        continue
    digest, rel = line.split("  ", 1)
    entries[rel] = digest
actual = {p.relative_to(ROOT).as_posix(): sha256_file(p)
          for p in ROOT.rglob("*") if p.is_file() and p.name != "checksums.sha256"}
missing = set(actual) - set(entries)
extra = set(entries) - set(actual)
stale = {k for k in set(actual) & set(entries) if actual[k] != entries[k]}
print(f"[checksums] entries={len(entries)} actual={len(actual)} "
      f"missing={len(missing)} extra={len(extra)} stale={len(stale)}")
if missing or extra or stale:
    problems.append(f"checksums mismatch: missing={sorted(missing)[:3]} extra={sorted(extra)[:3]} stale={sorted(stale)[:3]}")

# 2) tasks_index.csv must list exactly the packages on disk, with correct counts
rows = list(csv.DictReader((INDEX / "tasks_index.csv").read_text(encoding="utf-8").splitlines()))
print(f"[tasks_index] rows={len(rows)}")
if [r["task_id"] for r in rows] != TASKS:
    problems.append(f"tasks_index lists {[r['task_id'] for r in rows]}, expected {TASKS}")
for row in rows:
    task_id = row["task_id"]
    items = json.loads((ROOT / task_id / "tests" / "required_testcases.json").read_text(encoding="utf-8-sig"))
    f2p = sum(1 for i in items if i["group"] == "F2P")
    p2p = sum(1 for i in items if i["group"] == "P2P")
    if int(row["f2p"]) != f2p or int(row["p2p"]) != p2p:
        problems.append(f"{task_id}: csv f2p/p2p {row['f2p']}/{row['p2p']} != manifest {f2p}/{p2p}")
    expected_hash = tree_hash(ROOT / task_id)
    mark = "OK" if row["task_hash"] == expected_hash else "MISMATCH"
    print(f"  {task_id}: f2p={f2p} p2p={p2p} task_hash {mark}")
    if row["task_hash"] != expected_hash:
        problems.append(f"{task_id}: task_hash not reproducible")

# 3) model_validation_summary.json must agree with qualification summaries
mv = json.loads((INDEX / "model_validation_summary.json").read_text(encoding="utf-8-sig"))
for entry in mv["tasks"]:
    task_id = entry["task_id"]
    q = json.loads((ROOT / task_id / "jobs" / "_index" / "qualification_summary.json")
                   .read_text(encoding="utf-8-sig"))
    opus = q["models"]["OPUS"]["score_sum"]
    qwen = q["models"]["QWEN"]["score_sum"]
    recorded = entry["models"]["opus-5"]["model_score_sum"]
    if recorded != opus:
        problems.append(f"{task_id}: summary opus {recorded} != qualification {opus}")
    passed = entry["admission"]["passed"]
    print(f"  {task_id}: qwen={qwen} opus={opus} admission={'PASS' if passed else 'FAIL'}")
    if passed != bool(q["gates"]["opium_sum_greater_than_qwen"] if "opium_sum_greater_than_qwen" in q["gates"]
                      else q["gates"]["opus_sum_greater_than_qwen"]):
        problems.append(f"{task_id}: admission flag disagrees with qualification gates")

# 4) Files that describe the *current* state must not claim the old 9/16-task scope.
strict = [ROOT / "README.md", ROOT / "VALIDATION.md",
          INDEX / "validation_report.md", INDEX / "model_validation_report.md"]
scope_hits: list[str] = []
for path in strict:
    if not path.is_file():
        continue
    for num, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if re.search(r"(9|16)\s*(个)?\s*题包?", line) and not any(
                h in line for h in ("历史", "原按", "曾按", "完整仓库", "旧", "不适用", "属于", "不在本")):
            scope_hits.append(f"{path.relative_to(ROOT)}:{num}: {line.strip()[:110]}")
print(f"[scope] unlabelled old-scope claims in current-state docs: {len(scope_hits)}")
for hit in scope_hits:
    print("   !", hit)
if scope_hits:
    problems.append(f"{len(scope_hits)} unlabelled old-scope claims remain")

# 4b) Historical logs must instead carry an explicit scope declaration.
declarations = {
    INDEX / "CHANGELOG.md": "范围对齐 + 标准 Harbor 兼容",
    INDEX / "known_issues.md": "范围声明（2026-10-08）",
}
for path, marker in declarations.items():
    text = path.read_text(encoding="utf-8", errors="ignore")
    ok = marker in text
    print(f"[scope] {path.name} declares scope: {'yes' if ok else 'NO'}")
    if not ok:
        problems.append(f"{path.name} lacks its scope declaration marker")

print()
print("RESULT:", "PASS — materials match the two packages" if not problems else "FAIL")
for p in problems:
    print("  -", p)
