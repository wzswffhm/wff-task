"""217 加深（第二步）：候选代码注入 3 处契约偏差 + 更新题面/元数据/版本。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
WS = TASK / "environment/workspace/WReparse"
failed = False


def patch(path: Path, old: str, new: str, label: str) -> None:
    global failed
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {path.name}: {label} 命中 {n} 次")
        failed = True
        return
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {path.name}: {label}")


# ------------------------------------------------ 候选代码注入 3 处新偏差
patch(WS / "Walker.ps1",
      "        MaxDepth = [Math]::Max(0, $MaxDepth)",
      "        MaxDepth = $MaxDepth",
      "偏差1: 去掉 MaxDepth 的负数下限（契约 §4.3）")

patch(WS / "Walker.ps1",
      "                Invoke-WReparseDirectoryWalk -RealDirectory $resolved -VirtualDirectory $virtualChild `",
      "                Invoke-WReparseDirectoryWalk -RealDirectory $resolved -VirtualDirectory $resolved `",
      "偏差2: 跟随链接时用真实目标路径命名子项（契约 §4.2）")

patch(WS / "Walker.ps1",
      "    catch {\n"
      "        Add-WReparseError -State $state -RelativePath '.' -Code 'invalid_argument' -Message $_.Exception.Message\n"
      "        return [pscustomobject]@{ Records = @(); Errors = $state.Errors.ToArray(); Skipped = 0 }\n"
      "    }",
      "    catch {\n"
      "        return [pscustomobject]@{ Records = @(); Errors = @(); Skipped = 0 }\n"
      "    }",
      "偏差3: 吞掉规范化异常，不报 invalid_argument（契约 §7）")

# ------------------------------------------------------------- task.toml 版本
patch(TASK / "task.toml",
      'name = "wfflab/wreparse-217"\nversion = "1.0.0"',
      'name = "wfflab/wreparse-217"\nversion = "1.1.0"',
      "task.toml [task].version -> 1.1.0")

# ------------------------------------------------- required_testcases 新增 6
rt = TASK / "tests/required_testcases.json"
items = json.loads(rt.read_text(encoding="utf-8-sig"))
new_cases = [
    ("f2p-negative-maxdepth-is-treated-as-zero", "F2P"),
    ("f2p-invalid-root-reports-invalid-argument", "F2P"),
    ("f2p-follow-uses-link-path-prefix", "F2P"),
    ("p2p-follow-file-link-produces-no-children", "P2P"),
    ("p2p-repeated-target-in-sibling-branch-is-not-a-cycle", "P2P"),
    ("p2p-empty-tree-serialises-empty-arrays", "P2P"),
]
existing = {i["id"] for i in items}
for cid, grp in new_cases:
    if cid not in existing:
        items.append({"id": cid, "group": grp})
rt.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
f2p = sum(1 for i in items if i["group"] == "F2P")
p2p = sum(1 for i in items if i["group"] == "P2P")
print(f"ok required_testcases.json: {len(items)} 条（F2P {f2p} + P2P {p2p}）")

# ----------------------------------------------------------------- rubric.json
rb = TASK / "tests/rubric.json"
doc = json.loads(rb.read_text(encoding="utf-8-sig"))
doc["task_version"] = "1.1.0"
add = {
    "traversal-safety": ["f2p-negative-maxdepth-is-treated-as-zero",
                         "f2p-follow-uses-link-path-prefix",
                         "p2p-follow-file-link-produces-no-children",
                         "p2p-repeated-target-in-sibling-branch-is-not-a-cycle"],
    "diagnostics": ["f2p-invalid-root-reports-invalid-argument"],
    "determinism": ["p2p-empty-tree-serialises-empty-arrays"],
}
for item in doc["items"]:
    for tid in add.get(item["rubric_id"], []):
        if tid not in item["test_ids"]:
            item["test_ids"].append(tid)
# 扩充 pass_condition，使其覆盖新增判定
for item in doc["items"]:
    if item["rubric_id"] == "traversal-safety":
        item["pass_condition"] += (" A negative -MaxDepth behaves exactly like 0; in follow mode entries reached "
                                   "through a link are named with the link path prefix and a link to a file yields "
                                   "no children; a target already visited on a sibling branch is not a cycle.")
    elif item["rubric_id"] == "diagnostics":
        item["pass_condition"] += " A root that cannot be normalised yields 'invalid_argument'."
    elif item["rubric_id"] == "determinism":
        item["pass_condition"] += " An empty tree serialises Records and Errors as []."
rb.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"ok rubric.json: task_version=1.1.0, items={len(doc['items'])}, "
      f"test_ids={sum(len(i['test_ids']) for i in doc['items'])}")

# -------------------------------------------------------------- instruction.md
ins = TASK / "instruction.md"
text = ins.read_text(encoding="utf-8")
old_tail = """6. 扫描根不存在时报 `not_found`，扫描根是文件时报 `structure`。"""
new_tail = """6. 扫描根不存在时报 `not_found`，扫描根是文件时报 `structure`；扫描根字符串无法规范化时报
   `invalid_argument`。
7. `-MaxDepth` 传负数与传 0 的行为**完全一致**（两者都对扫描根的直接子项报 `too_deep`）。
8. `-Follow` 下经链接进入的条目，其 `RelativePath` 以**链接路径**为前缀（例如 `link-in\\readme.txt`），
   而不是以真实目标路径命名。
9. `-Follow` 下目标为**文件**的链接只登记链接条目自身，不产生任何子项。
10. 同一个目标被**兄弟分支**上的两个链接分别指向时**不构成环**：两个分支都应被正常进入，
    且 `Errors` 中不得出现针对它们的 `cycle`。
11. 扫描一棵**空目录**树时，序列化结果中 `Records` 与 `Errors` 均为 `[]`。"""
if old_tail not in text:
    print("!! instruction.md: 未找到验收清单尾部")
    failed = True
else:
    text = text.replace(old_tail, new_tail)
    # 同步「必须满足的行为」第 8 条，明确 invalid_argument 也在契约 §7 内
    text = text.replace(
        "8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致；未给 `-Follow` 时不得产生\n"
        "   `cycle` 与 `broken_target`。",
        "8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致（含 `invalid_argument`）；\n"
        "   未给 `-Follow` 时不得产生 `cycle` 与 `broken_target`。")
    # 边界情形清单补上新夹具
    text = text.replace(
        "指向扫描根之外的链接、循环链接与悬空目标、仅前缀相同的兄弟目录，以及同一棵树重复\n"
        "序列化的一致性。",
        "指向扫描根之外的链接、循环链接与悬空目标、仅前缀相同的兄弟目录、**目标为文件的链接**、\n"
        "**指向同一目标的兄弟链接**、**空目录**，以及同一棵树重复序列化的一致性。")
    ins.write_text(text, encoding="utf-8")
    print("ok instruction.md: 新增验收条目 7-11 并同步边界情形清单")

print("\nRESULT:", "部分失败" if failed else "第二步完成")
sys.exit(1 if failed else 0)
