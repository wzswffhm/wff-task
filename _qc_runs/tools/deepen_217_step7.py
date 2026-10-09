"""217 加深（第七步）：同步元数据。

  required_testcases.json  30 -> 36（新增 5 F2P / 1 P2P）
  rubric.json              新增 public-surface 项，权重合计仍为 1.0，版本 -> 1.2.0
  task.toml                difficulty L3 -> L4（对齐 215 的难度设计），版本 -> 1.2.0

新增检查与契约条款的对应（全部为契约已声明内容，未越界）：
  f2p-sorting-is-culture-independent            §6.1 / §6.2
  f2p-module-exports-exactly-six-functions      §2
  p2p-target-is-serialised-as-string            §3.1（Target 为单个目标串）
  f2p-report-has-exactly-contract-fields        §3
  f2p-no-follow-produces-no-cycle-or-broken-target  §7
  f2p-inscope-is-false-for-non-reparse-entries  §3.1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
failed = False

NEW_TESTS = [
    ("f2p-sorting-is-culture-independent", "F2P"),
    ("f2p-module-exports-exactly-six-functions", "F2P"),
    ("p2p-target-is-serialised-as-string", "P2P"),
    ("f2p-report-has-exactly-contract-fields", "F2P"),
    ("f2p-no-follow-produces-no-cycle-or-broken-target", "F2P"),
    ("f2p-inscope-is-false-for-non-reparse-entries", "F2P"),
]

# ------------------------------------------------------- required_testcases.json
path = TASK / "tests/required_testcases.json"
cases = json.loads(path.read_text(encoding="utf-8"))
before = (len(cases), sum(1 for c in cases if c["group"] == "F2P"), sum(1 for c in cases if c["group"] == "P2P"))
existing = {c["id"] for c in cases}
for tid, group in NEW_TESTS:
    if tid in existing:
        print(f"!! {tid} 已存在")
        failed = True
        continue
    cases.append({"id": tid, "group": group})
path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
after = (len(cases), sum(1 for c in cases if c["group"] == "F2P"), sum(1 for c in cases if c["group"] == "P2P"))
print(f"ok required_testcases.json: {before} -> {after} (总数, F2P, P2P)")

# ------------------------------------------------------------------- rubric.json
path = TASK / "tests/rubric.json"
rubric = json.loads(path.read_text(encoding="utf-8"))
rubric["task_version"] = "1.2.0"

reweight = {
    "traversal-safety": 0.18,
    "containment": 0.13,
    "link-target-resolution": 0.13,
    "entry-classification": 0.16,
    "enumeration": 0.08,
    "determinism": 0.12,
    "accounting": 0.04,
    "diagnostics": 0.04,
}
for item in rubric["items"]:
    rid = item["rubric_id"]
    if rid in reweight:
        item["weight"] = reweight[rid]
    else:
        print(f"!! rubric 项 {rid} 没有新权重")
        failed = True

by_id = {item["rubric_id"]: item for item in rubric["items"]}

# 排序的 culture 独立性归入 determinism
by_id["determinism"]["test_ids"].append("f2p-sorting-is-culture-independent")
by_id["determinism"]["pass_condition"] += (
    " The ordering must be culture-independent: names that a culture-aware collation"
    " would reorder by base letter (for example an ASCII 'Z' against a Latin-1"
    " umlaut) must still follow ordinal-ignore-case."
)
by_id["determinism"]["failure_reason"] += (
    " Ordering is delegated to a culture-aware default sort, so non-ASCII names land"
    " in a host-dependent position."
)

# 未跟随不得产生 cycle / broken_target 归入 traversal-safety
by_id["traversal-safety"]["test_ids"].append("f2p-no-follow-produces-no-cycle-or-broken-target")
by_id["traversal-safety"]["pass_condition"] += (
    " Without -Follow neither 'cycle' nor 'broken_target' may appear in Errors."
)
by_id["traversal-safety"]["failure_reason"] += (
    " A default scan resolves targets anyway and reports cycle or broken_target."
)

# 普通条目 InScope 恒为 false 归入 entry-classification
by_id["entry-classification"]["test_ids"].append("f2p-inscope-is-false-for-non-reparse-entries")
by_id["entry-classification"]["pass_condition"] += (
    " InScope is only meaningful for reparse entries and is false on every ordinary"
    " file and directory."
)
by_id["entry-classification"]["failure_reason"] += (
    " Ordinary entries also carry a computed InScope value."
)

# 新增 public-surface 项：模块导出面 + 报告字段集合
public_surface = {
    "rubric_id": "public-surface",
    "description": "The module publishes exactly the six contract functions and the report carries exactly the contract fields.",
    "type": "programmatic",
    "weight": 0.12,
    "test_ids": [
        "f2p-module-exports-exactly-six-functions",
        "f2p-report-has-exactly-contract-fields",
        "p2p-target-is-serialised-as-string",
    ],
    "evidence_source": "results/result.json",
    "pass_condition": "The imported module exposes exactly Get-WReparseReport, ConvertTo-WReparseJson, Get-WReparseSchemaVersion, Test-WReparseWithinRoot, Get-WReparseCanonicalPath and Resolve-WReparseLinkTarget, with no internal helper leaking into the surface. The report object carries exactly SchemaVersion, Root, Records, Errors and Stats - no extra field such as a generation timestamp. A record's Target is a single target string.",
    "failure_reason": "Internal helpers are exported alongside the six contract functions, the report object carries fields the contract does not define, or Target is left as whatever shape the provider returned.",
}
rubric["items"].append(public_surface)

total = round(sum(item["weight"] for item in rubric["items"]), 6)
rubric["total_weight"] = total
path.write_text(json.dumps(rubric, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"ok rubric.json: {len(rubric['items'])} 项, task_version=1.2.0, 权重合计={total}")
if abs(total - 1.0) > 1e-9:
    print(f"!! 权重合计不是 1.0: {total}")
    failed = True

# 每个 testcase 必须恰好被一个 rubric 项覆盖
covered = [t for item in rubric["items"] for t in item["test_ids"]]
declared = [c["id"] for c in cases]
missing = [t for t in declared if t not in covered]
extra = [t for t in covered if t not in declared]
if missing:
    print(f"!! 未被 rubric 覆盖的 testcase: {missing}")
    failed = True
if extra:
    print(f"!! rubric 引用了未声明的 testcase: {extra}")
    failed = True
if len(covered) != len(set(covered)):
    dupes = sorted({t for t in covered if covered.count(t) > 1})
    print(f"!! testcase 被多个 rubric 项覆盖: {dupes}")
    failed = True
if not missing and not extra:
    print(f"ok rubric 覆盖: {len(declared)} 个 testcase 全部一对一登记")

# --------------------------------------------------------------------- task.toml
path = TASK / "task.toml"
text = path.read_text(encoding="utf-8")
for old, new, label in (
    ('difficulty = "L3"', 'difficulty = "L4"', "difficulty L3 -> L4"),
    ('version = "1.1.0"', 'version = "1.2.0"', "[task].version -> 1.2.0"),
):
    n = text.count(old)
    if n != 1:
        print(f"!! task.toml: {label} 命中 {n} 次")
        failed = True
        continue
    text = text.replace(old, new)
    print(f"ok task.toml: {label}")
path.write_text(text, encoding="utf-8")

print("\nRESULT:", "部分失败" if failed else "第七步完成")
sys.exit(1 if failed else 0)
