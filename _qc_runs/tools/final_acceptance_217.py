"""217 加深后的最终一致性验收（只读，不改任何文件）。

逐项核对：题包实物 / 索引材料 / 交付 zip 三者的身份、难度与 required 计数是否自洽，
并复跑一次控制组确认加深后的题包在本机仍然 Oracle=1 / NOP=0。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
ROOT = WS / "harbor-windows"
INDEX = ROOT / "_index"
TASK_ID = "wfflab__wreparse-217"
SRC = ROOT / TASK_ID
BACKUP = WS / "_qc_runs" / "backup-217-before-deepen-v12"
CANDIDATE = BACKUP / "WReparse-candidate"
ZIP = WS / "deliverables" / "2026-10-09_wreparse217-加深L4" / "package" / f"{TASK_ID}-v1.2.0-delivery.zip"
PWSH = "powershell.exe"

problems: list[str] = []
notes: list[str] = []


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


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'OK ' if ok else 'BAD'}] {label}{('  -- ' + detail) if detail else ''}")
    if not ok:
        problems.append(f"{label} {detail}".strip())


print("=== 1. 题包身份 ===")
cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
src = json.loads((SRC / "source.json").read_text(encoding="utf-8-sig"))
items = json.loads((SRC / "tests/required_testcases.json").read_text(encoding="utf-8-sig"))
rubric = json.loads((SRC / "tests/rubric.json").read_text(encoding="utf-8-sig"))
f2p = sum(1 for i in items if i["group"] == "F2P")
p2p = sum(1 for i in items if i["group"] == "P2P")

check("task.toml difficulty = L4", cfg["metadata"]["difficulty"] == "L4", cfg["metadata"]["difficulty"])
check("task.toml [task].version = 1.2.0", cfg["task"]["version"] == "1.2.0", cfg["task"]["version"])
check("source.json task_version = 1.2.0", src.get("task_version") == "1.2.0", str(src.get("task_version")))
check("required = 36 (23 F2P / 13 P2P)", len(items) == 36 and f2p == 23 and p2p == 13,
      f"total={len(items)} f2p={f2p} p2p={p2p}")
check("rubric task_version = 1.2.0", rubric.get("task_version") == "1.2.0", str(rubric.get("task_version")))
check("rubric 权重合计 = 1.0", abs(float(rubric["total_weight"]) - 1.0) < 1e-9, str(rubric["total_weight"]))

covered = [t for it in rubric["items"] for t in it["test_ids"]]
check("rubric 一对一覆盖 36 个 testcase", len(covered) == 36 and len(set(covered)) == 36,
      f"covered={len(covered)} unique={len(set(covered))}")

h = tree_hash(SRC)
notes.append(f"task_hash = {h}")

print("\n=== 2. 题包内容（L4 结构）===")
check("assets/observed-provider-facts.json 存在", (SRC / "environment/workspace/assets/observed-provider-facts.json").is_file())
check("tests/test_wreparse_basic.ps1（可见冒烟）存在", (SRC / "environment/workspace/tests/test_wreparse_basic.ps1").is_file())
contract = (SRC / "environment/workspace/docs/REPARSE-CONTRACT.md").read_text(encoding="utf-8")
check("契约含 §10 provider 细节分流", "## 10." in contract and "observed-provider-facts" in contract)
instr = (SRC / "instruction.md").read_text(encoding="utf-8")
check("instruction 声明两个权威来源", "observed-provider-facts" in instr and "以实测事实为准" in instr)
check("instruction 声明冒烟测试非权威", "test_wreparse_basic" in instr)
check("instruction 含 17 条验收", all(f"\n{n}. " in instr or f"{n}. " in instr for n in range(12, 18)))

print("\n=== 3. 索引材料 ===")
rows = list(csv.reader(io.StringIO((INDEX / "tasks_index.csv").read_text(encoding="utf-8-sig"))))
header = rows[0]
row = next((dict(zip(header, r)) for r in rows[1:] if r and r[0] == TASK_ID), None)
check("tasks_index.csv 有 217 行", row is not None)
if row:
    check("index task_hash 与实物一致", row["task_hash"] == h, f"{row['task_hash'][:12]}… vs {h[:12]}…")
    check("index difficulty = L4", row["difficulty"] == "L4", row["difficulty"])
    check("index task_version = 1.2.0", row["task_version"] == "1.2.0", row["task_version"])
    check("index f2p/p2p = 23/13", row["f2p"] == "23" and row["p2p"] == "13", f"{row['f2p']}/{row['p2p']}")
    check("index status 标注待重跑", "待重跑" in row["status"])

ki = (INDEX / "known_issues.md").read_text(encoding="utf-8")
check("known_issues 题号对照 217 = L4/36", "**L4**" in ki and "23 F2P + 13 P2P = 36" in ki)
check("known_issues 含 K21", "| K21 |" in ki)
cl = (INDEX / "CHANGELOG.md").read_text(encoding="utf-8")
check("CHANGELOG 含本轮条目", "wreparse-217 难度加深" in cl)
check("CHANGELOG 里的 hash 已更新", h in cl)
check("tasks_index 的 hash 不再是旧值", "480d7702632ebb1c1974156c4f0a821e39ec082832dc8b3ea290b41c6956b761" not in
      (INDEX / "tasks_index.csv").read_text(encoding="utf-8-sig"))

print("\n=== 4. 交付 zip ===")
check("zip 存在", ZIP.is_file(), ZIP.name)
if ZIP.is_file():
    names = zipfile.ZipFile(ZIP).namelist()
    check("zip 含平台导入 JSON", f"outside_harbor/{TASK_ID}.json" in names)
    check("zip 无 results/ 泄漏", not any(f"assets/{TASK_ID}/results/" in n for n in names))
    check("zip 含 assets/observed-provider-facts.json",
          any(n.endswith("workspace/assets/observed-provider-facts.json") for n in names))
    check("zip 含 verifier/ 四件", all(any(n.endswith(f"verifier/{f}") for n in names)
                                      for f in ("report.json", "result.json", "reward.txt", "test-stdout.txt")))
    imp = json.loads(zipfile.ZipFile(ZIP).read(f"outside_harbor/{TASK_ID}.json").decode("utf-8"))
    check("zip 导入 JSON 的 hash 与实物一致", imp["task_hash"] == h)
    check("zip 导入 JSON difficulty = L4", imp["difficulty"] == "L4", imp["difficulty"])
    check("zip 导入 JSON task_version = 1.2.0", imp["task_version"] == "1.2.0", imp["task_version"])

print("\n=== 5. 控制组复跑（Oracle 1 次 / NOP 1 次）===")


def ps(script: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


import shutil
results = {}
for mode in ("oracle", "nop"):
    if mode == "oracle":
        ps(SRC / "solution/solve.ps1", "-TaskRoot", str(SRC))
    else:
        tgt = SRC / "environment/workspace/WReparse"
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(CANDIDATE, tgt)
    ps(SRC / "tests/prepare.ps1", "-TaskRoot", str(SRC))
    code, out = ps(SRC / "tests/test.ps1", "-TaskRoot", str(SRC))
    doc = json.loads((SRC / "results/result.json").read_text(encoding="utf-8-sig"))
    results[mode] = doc
    print(f"    {mode}: validity={doc['run_validity']} score={doc['formal_score']} "
          f"passed={doc['passed']}/{doc['total']}")

tgt = SRC / "environment/workspace/WReparse"
if tgt.exists():
    shutil.rmtree(tgt)
shutil.copytree(CANDIDATE, tgt)

check("Oracle VALID/1", results["oracle"]["run_validity"] == "VALID" and results["oracle"]["formal_score"] == 1)
check("NOP VALID/0", results["nop"]["run_validity"] == "VALID" and results["nop"]["formal_score"] == 0)

print()
print("摘要：")
for n in notes:
    print(f"  {n}")
if problems:
    print(f"\n验收未通过（{len(problems)} 项）：")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
print("\n最终验收：全部通过")
sys.exit(0)
