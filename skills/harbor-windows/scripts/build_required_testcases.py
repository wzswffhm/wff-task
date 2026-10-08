# -*- coding: utf-8 -*-
"""build_required_testcases.py —— 生成甲方 QC 要求的 `tests/required_testcases.json`

甲方 `windows-harbor-qc` 的 checklist 第 1 节把 `tests/required_testcases.json`
列为 Task 根目录**必备**文件；`run_qc.py` 的静态检查要求它是**非空列表**，
每项形如 `{"id": "<testcase id>", "group": "F2P" | "P2P"}`，且**必须同时含 F2P 与 P2P**。

本脚本从题包**既有证据**推导分组，不臆造：

* `--from-checks <candidate.json> <golden.json>`
  用「未打补丁工作区」与「已应用 Golden」两端逐项 `checks.json` 对比：
  `candidate=FAIL 且 golden=PASS` → **F2P**；`两端都 PASS` → **P2P**。
  适用于本机判分链路留有对照明细的题（如 wreparse-217）。
* `--from-spec <swelive_spec.json>`
  直接读 spec 的 `FAIL_TO_PASS` / `PASS_TO_PASS`（pytest node id 形态），
  归一化成题包 `tests/rubric.json` 使用的短 id（去 `test_` 前缀、`_` 换 `-`）。
  适用于平台导入包内留有 spec 的题（如 wfmt-215）。

输出顺序固定按 `tests/rubric.json` 的 `items[].test_ids` 展开顺序，保证稳定可复现。

用法：
    python build_required_testcases.py --task-dir <题包> \
        --from-checks <candidate checks.json> <golden checks.json> [--write]
    python build_required_testcases.py --task-dir <题包> \
        --from-spec <swelive_spec.json> [--write]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def rubric_order(task_dir: str) -> list[str]:
    """按 rubric.json 的 items 顺序展开全部 test_id。"""
    rubric = read_json(os.path.join(task_dir, "tests", "rubric.json"))
    ids: list[str] = []
    for item in rubric.get("items") or []:
        for tid in item.get("test_ids") or []:
            ids.append(tid)
    return ids


def groups_from_checks(candidate: str, golden: str) -> dict[str, str]:
    cand = {c["test_id"]: c["status"] for c in read_json(candidate)["checks"]}
    gold = {c["test_id"]: c["status"] for c in read_json(golden)["checks"]}
    out: dict[str, str] = {}
    for tid, cstatus in cand.items():
        gstatus = gold.get(tid)
        if cstatus == "FAIL" and gstatus == "PASS":
            out[tid] = "F2P"
        elif cstatus == "PASS" and gstatus == "PASS":
            out[tid] = "P2P"
        else:
            raise SystemExit(f"非标准对照组合，拒绝生成：{tid} candidate={cstatus} golden={gstatus}")
    return out


def short_id(node: str) -> str:
    name = node.split("::")[-1]
    if name.startswith("test_"):
        name = name[5:]
    return name.replace("_", "-")


def groups_from_spec(spec_path: str) -> dict[str, str]:
    spec = read_json(spec_path)
    f2p = spec.get("FAIL_TO_PASS") or []
    p2p = spec.get("PASS_TO_PASS") or []
    if not f2p or not p2p:
        raise SystemExit(f"spec 缺 FAIL_TO_PASS / PASS_TO_PASS：{spec_path}")
    out: dict[str, str] = {}
    for node in f2p:
        out[short_id(node)] = "F2P"
    for node in p2p:
        out[short_id(node)] = "P2P"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 tests/required_testcases.json")
    ap.add_argument("--task-dir", required=True, help="题包目录")
    ap.add_argument("--from-checks", nargs=2, metavar=("CANDIDATE", "GOLDEN"),
                    help="未修复 / Golden 两端 checks.json")
    ap.add_argument("--from-spec", metavar="SPEC", help="swelive_spec.json")
    ap.add_argument("--write", action="store_true", help="实际写入（默认仅预览）")
    args = ap.parse_args()

    task_dir = os.path.abspath(args.task_dir)
    if not os.path.isfile(os.path.join(task_dir, "task.toml")):
        raise SystemExit(f"不是题包目录（缺 task.toml）：{task_dir}")
    if bool(args.from_checks) == bool(args.from_spec):
        raise SystemExit("必须且只能指定 --from-checks 或 --from-spec 之一")

    if args.from_checks:
        group_map = groups_from_checks(*args.from_checks)
        source = "checks 对照：" + " / ".join(os.path.basename(p) for p in args.from_checks)
    else:
        group_map = groups_from_spec(args.from_spec)
        source = "spec：" + os.path.basename(args.from_spec)

    order = rubric_order(task_dir)
    missing = [i for i in order if i not in group_map]
    extra = [i for i in group_map if i not in order]
    if missing:
        raise SystemExit(f"rubric 中的 testcase 缺分组依据，拒绝生成：{missing}")
    if extra:
        raise SystemExit(f"分组依据里有 rubric 未声明的 testcase，请核对：{extra}")

    manifest = [{"id": tid, "group": group_map[tid]} for tid in order]
    f2p = sum(1 for m in manifest if m["group"] == "F2P")
    p2p = sum(1 for m in manifest if m["group"] == "P2P")
    if not f2p or not p2p:
        raise SystemExit("清单必须同时含 F2P 与 P2P")

    out_path = os.path.join(task_dir, "tests", "required_testcases.json")
    body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    print(f"题包      : {task_dir}")
    print(f"依据      : {source}")
    print(f"清单      : {len(manifest)} 项（F2P {f2p} / P2P {p2p}）")
    print(f"目标      : {out_path}")
    if args.write:
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        print("已写入")
    else:
        print("（预览模式：加 --write 才会落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
