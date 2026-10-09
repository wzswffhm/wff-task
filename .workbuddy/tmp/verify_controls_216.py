# -*- coding: utf-8 -*-
"""wchunk-216 本机控制组验证：Oracle ×N + NOP ×N。

甲方 QC 硬门禁：
  Oracle N 次全部 VALID / score=1（checks 18 passed 0 failed）
  NOP    N 次全部 VALID / score=0（checks 必须有 FAIL，且 rubric 有未满足项）

每轮都重新应用 Gold 或恢复候选，再完整走 environment/prepare.ps1 +
tests/test.ps1，读 results/checks.json 判定，不使用任何缓存结论。

全程在**隔离副本**上运行，不修改题包本体（原题包只作为候选来源被读取）。

用法：
  python verify_controls_216.py                 # 3+3
  python verify_controls_216.py --rounds 1      # 冒烟
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-windows" / "wfflab__wchunk-216"
OUT = REPO / "_qc_runs" / "controls_216_v100.json"
PWSH = "powershell.exe"


def run_ps(script: pathlib.Path, *args: str) -> tuple[int, str]:
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def read_checks(root: pathlib.Path) -> dict | None:
    path = root / "results" / "checks.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    checks = doc.get("checks") or []
    failed = [c for c in checks if c.get("status") != "PASS"]
    return {
        "task_id": doc.get("task_id"),
        "task_version": doc.get("task_version"),
        "total": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "failed_ids": [c.get("test_id") for c in failed],
    }


def restore_candidate(stage: pathlib.Path) -> None:
    """从原题包把候选 wchunk 包复制回副本（NOP 的前提）。"""
    target = stage / "environment" / "workspace" / "wchunk"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TASK / "environment" / "workspace" / "wchunk", target)


def run_round(stage: pathlib.Path, mode: str, index: int) -> dict:
    # 每轮重置工作区状态
    results = stage / "results"
    if results.exists():
        shutil.rmtree(results)
    if mode == "oracle":
        code, out = run_ps(stage / "solution" / "solve.ps1", "-TaskRoot", str(stage))
        if code != 0:
            return {"mode": mode, "index": index, "error": f"solve failed: {out[-300:]}"}
    else:
        restore_candidate(stage)

    run_ps(stage / "environment" / "prepare.ps1", "-TaskRoot", str(stage))
    test_code, test_out = run_ps(stage / "tests" / "test.ps1", "-TaskRoot", str(stage))
    summary = read_checks(stage)
    if summary is None:
        return {"mode": mode, "index": index, "error": "results/checks.json missing",
                "tail": test_out[-400:]}
    summary.update({"mode": mode, "index": index, "test_exit": test_code})
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    stage = pathlib.Path(tempfile.mkdtemp(prefix="wchunk216-ctl-"))
    print(f"隔离副本: {stage}")
    shutil.copytree(TASK, stage, dirs_exist_ok=True)

    rounds: list[dict] = []
    try:
        for mode in ("oracle", "nop"):
            for i in range(1, args.rounds + 1):
                r = run_round(stage, mode, i)
                rounds.append(r)
                if "error" in r:
                    print(f"  {mode:6s} #{i}: ERROR {r['error']}")
                else:
                    print(f"  {mode:6s} #{i}: {r['task_id']} v{r['task_version']} "
                          f"total={r['total']} passed={r['passed']} failed={r['failed']} "
                          f"exit={r['test_exit']}")
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    problems: list[str] = []
    oracle = [r for r in rounds if r["mode"] == "oracle"]
    nop = [r for r in rounds if r["mode"] == "nop"]

    for r in oracle:
        if "error" in r:
            problems.append(f"oracle#{r['index']} 执行失败: {r['error']}")
            continue
        if r["passed"] != r["total"]:
            problems.append(f"oracle#{r['index']} 未全过: {r['passed']}/{r['total']} "
                            f"failed={r['failed_ids']}")
        if r["failed"] != 0:
            problems.append(f"oracle#{r['index']} failed={r['failed']}（须 0）")
        if r["test_exit"] != 0:
            problems.append(f"oracle#{r['index']} exit={r['test_exit']}（须 0）")

    for r in nop:
        if "error" in r:
            problems.append(f"nop#{r['index']} 执行失败: {r['error']}")
            continue
        if r["failed"] == 0:
            problems.append(f"nop#{r['index']} 全过（须有 FAIL，score=0）")
        if r["test_exit"] == 0:
            problems.append(f"nop#{r['index']} exit=0（须非 0）")

    versions = {r.get("task_version") for r in rounds if "error" not in r}
    if versions != {"1.0.0"}:
        problems.append(f"task_version 不一致或非 1.0.0: {versions}")
    ids = {r.get("task_id") for r in rounds if "error" not in r}
    if ids != {"wfflab__wchunk-216"}:
        problems.append(f"task_id 不一致: {ids}")

    out = {
        "task_id": "wfflab__wchunk-216",
        "task_version": "1.0.0",
        "rounds": rounds,
        "gates": {
            "oracle_all_pass": all(
                "error" not in r and r["failed"] == 0 and r["passed"] == r["total"]
                for r in oracle) and bool(oracle),
            "nop_all_score_zero": all(
                "error" not in r and r["failed"] > 0 and r["test_exit"] != 0
                for r in nop) and bool(nop),
            "task_identity_consistent": versions == {"1.0.0"} and ids == {"wfflab__wchunk-216"},
        },
        "problems": problems,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n证据已写入: {OUT}")
    for key, value in out["gates"].items():
        print(f"  {key} = {value}")
    if problems:
        print("\n未通过：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\n控制组门禁全部符合（Oracle {args.rounds}×1、NOP {args.rounds}×0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
