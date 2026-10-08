# -*- coding: utf-8 -*-
"""align_report_protocol.py —— 把题包判分产物对齐甲方 QC（windows-harbor-qc）协议

甲方 `run_trials.py: formal_result` 接受的三套协议里，与本项目结构最契合的是
**aggregate-v1**（`run_trials.py:57-84`），其硬性要求：

```text
report.schema_version == "aggregate-v1"
report.run_validity   == "VALID"
report.total / passed / failed / invalid 均为 int，invalid == 0
report.formal_score   == int(passed == total)，且与 Harbor reward 一致
report.cases          == [{"test_id": "f2p-…"|"p2p-…", "passed": bool}]
rubric.items[].test_ids 展开后必须与 cases 的 test_id 集合完全相等，
且**每一项都必须以 `f2p-` 或 `p2p-` 开头**（`run_trials.py:74`）
```

因此 `tests/rubric.json` 的 `test_ids` 必须带 `f2p-` / `p2p-` 前缀，而
`tests/run_tests.ps1` 产出的 `checks.json` 用的是**裸 id**，聚合脚本需要剥前缀匹配。

本脚本负责两件纯数据工作（不触碰 PowerShell 逻辑）：

1. 给 `tests/rubric.json` 的 `test_ids` 统一加 `f2p-` / `p2p-` 前缀（幂等）；
2. 重建 `tests/required_testcases.json`（带前缀 id + group，供协议 B 与静态检查使用）。

分组依据必须来自既有证据，不臆造：

    --from-checks <candidate checks.json> <golden checks.json>
        candidate == FAIL 且 golden == PASS → f2p；两端均 PASS → p2p
    --from-spec <swelive_spec.json>
        读 FAIL_TO_PASS / PASS_TO_PASS（pytest node id 归一化为 rubric 短 id）

用法：
    python align_report_protocol.py --task-dir <题包> --from-checks <c> <g> [--write]
    python align_report_protocol.py --task-dir <题包> --from-spec <spec>      [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_required_testcases import groups_from_checks, groups_from_spec  # noqa: E402

PREFIX_RE = re.compile(r"^(f2p|p2p)-", re.I)


def read_json(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: str, value) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def sync_judge_hash(task_dir: str, rubric_path: str) -> str:
    """judge.toml 的 source_sha256 必须等于 rubric.json 的 sha256。

    改写 rubric.json 后不同步这里，甲方 QC 的静态检查会报
    "judge.toml rubric hash does not match rubric.json"（run_qc.py:246-252）。
    """
    judge_path = os.path.join(task_dir, "tests", "judge.toml")
    if not os.path.isfile(judge_path):
        return "judge.toml 不存在，跳过"
    fresh = hashlib.sha256(open(rubric_path, "rb").read()).hexdigest()
    with open(judge_path, encoding="utf-8") as fh:
        text = fh.read()
    new_text, count = re.subn(
        r'(source_sha256\s*=\s*")[0-9a-fA-F]{64}(")', r"\g<1>" + fresh + r"\g<2>", text
    )
    if count == 0:
        return "judge.toml 无 source_sha256 字段，跳过"
    if new_text == text:
        return f"judge.toml source_sha256 已是最新 ({fresh[:12]}…)"
    with open(judge_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    return f"judge.toml source_sha256 -> {fresh[:12]}…（已同步）"


def main() -> int:
    ap = argparse.ArgumentParser(description="对齐甲方 QC 的报告协议（rubric 前缀 + 清单）")
    ap.add_argument("--task-dir", required=True)
    ap.add_argument("--from-checks", nargs=2, metavar=("CANDIDATE", "GOLDEN"))
    ap.add_argument("--from-spec", metavar="SPEC")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    task_dir = os.path.abspath(args.task_dir)
    rubric_path = os.path.join(task_dir, "tests", "rubric.json")
    if not os.path.isfile(rubric_path):
        raise SystemExit(f"缺 tests/rubric.json：{task_dir}")
    if bool(args.from_checks) == bool(args.from_spec):
        raise SystemExit("必须且只能指定 --from-checks 或 --from-spec 之一")

    if args.from_checks:
        group_map = groups_from_checks(*args.from_checks)
        source = "checks 对照"
    else:
        group_map = groups_from_spec(args.from_spec)
        source = "swelive_spec"

    rubric = read_json(rubric_path)
    items = rubric.get("items") or []
    if not items:
        raise SystemExit("rubric.json 没有 items")

    changed = 0
    manifest = []
    seen: list[str] = []
    for item in items:
        new_ids = []
        for tid in item.get("test_ids") or []:
            bare = PREFIX_RE.sub("", tid)
            if bare not in group_map:
                raise SystemExit(f"testcase 缺分组依据，拒绝改写：{bare}")
            group = group_map[bare]
            prefixed = f"{group.lower()}-{bare}"
            if tid != prefixed:
                changed += 1
            new_ids.append(prefixed)
            manifest.append({"id": prefixed, "group": group})
            seen.append(prefixed)
        item["test_ids"] = new_ids

    if len(seen) != len(set(seen)):
        raise SystemExit("前缀化后出现重复 testcase id，拒绝写入")
    groups = {m["group"] for m in manifest}
    if groups != {"F2P", "P2P"}:
        raise SystemExit(f"清单必须同时含 F2P 与 P2P，实际：{sorted(groups)}")

    f2p = sum(1 for m in manifest if m["group"] == "F2P")
    p2p = sum(1 for m in manifest if m["group"] == "P2P")
    rt_path = os.path.join(task_dir, "tests", "required_testcases.json")

    print(f"题包    : {task_dir}")
    print(f"依据    : {source}")
    print(f"testcase: {len(manifest)} 项（F2P {f2p} / P2P {p2p}），本次改写 {changed} 个 id")
    print(f"样例    : {manifest[0]['id']} … {manifest[-1]['id']}")
    print(f"目标    : rubric.json -> 加前缀；required_testcases.json -> 重建")

    if args.write:
        write_json(rubric_path, rubric)
        write_json(rt_path, manifest)
        print("已写入")
        print("  " + sync_judge_hash(task_dir, rubric_path))
    else:
        print("（预览模式：加 --write 才落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
