"""217 加深后的本机控制组验证：Oracle ×3 + NOP ×3。

甲方 QC 硬门禁要求：
  Oracle 3 次全部 VALID/1（全部 required 通过）
  NOP    3 次全部 VALID/0（全部 P2P 通过，且至少一个核心 F2P 失败）

每轮都重新构建夹具并完整走 tests/test.ps1（run_tests + aggregate_results），
然后读 results/result.json 判定，不使用任何缓存结论。

用法：
  python verify_controls_217.py            # 完整 3+3
  python verify_controls_217.py --rounds 1 # 冒烟
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
BACKUP = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\backup-217-before-deepen-v12")
CANDIDATE = BACKUP / "WReparse-candidate"
PWSH = "powershell.exe"


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def restore_candidate() -> None:
    target = TASK / "environment/workspace/WReparse"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CANDIDATE, target)


def apply_golden() -> tuple[bool, str]:
    code, out = run_ps(TASK / "solution/solve.ps1", "-TaskRoot", str(TASK))
    return code == 0, out.strip()


def run_round(mode: str, index: int) -> dict:
    """mode: 'oracle' -> golden payload; 'nop' -> candidate payload."""
    if mode == "oracle":
        ok, msg = apply_golden()
        if not ok:
            return {"mode": mode, "index": index, "error": f"golden install failed: {msg}"}
    else:
        restore_candidate()

    code, out = run_ps(TASK / "tests/prepare.ps1", "-TaskRoot", str(TASK))
    code, out = run_ps(TASK / "tests/test.ps1", "-TaskRoot", str(TASK))

    result_path = TASK / "results/result.json"
    if not result_path.is_file():
        return {"mode": mode, "index": index, "error": "results/result.json missing"}

    doc = json.loads(result_path.read_text(encoding="utf-8-sig"))
    cases = doc.get("cases") or []
    passed = sum(1 for c in cases if c.get("passed"))
    failed = len(cases) - passed
    return {
        "mode": mode,
        "index": index,
        "run_validity": doc.get("run_validity"),
        "task_version": doc.get("task_version"),
        "total": doc.get("total"),
        "passed": passed,
        "failed": failed,
        "invalid": doc.get("invalid"),
        "formal_score": doc.get("formal_score"),
        "verdict": doc.get("verdict"),
        "test_exit": code,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()

    if not CANDIDATE.is_dir():
        print(f"候选备份不存在: {CANDIDATE}")
        return 2

    rounds: list[dict] = []
    for mode in ("oracle", "nop"):
        for i in range(1, args.rounds + 1):
            r = run_round(mode, i)
            rounds.append(r)
            mark = "" if "error" not in r else f"  !! {r['error']}"
            if "error" not in r:
                print(f"  {mode:6s} #{i}: validity={r['run_validity']:7s} "
                      f"total={r['total']} passed={r['passed']:2d} failed={r['failed']:2d} "
                      f"invalid={r['invalid']} score={r['formal_score']} exit={r['test_exit']}{mark}")
            else:
                print(f"  {mode:6s} #{i}: ERROR{mark}")

    restore_candidate()

    # ---- 判定 -----------------------------------------------------------------
    problems: list[str] = []
    oracle = [r for r in rounds if r["mode"] == "oracle"]
    nop = [r for r in rounds if r["mode"] == "nop"]

    for r in oracle:
        if "error" in r:
            problems.append(f"oracle#{r['index']} 执行失败: {r['error']}")
            continue
        if r["run_validity"] != "VALID":
            problems.append(f"oracle#{r['index']} run_validity={r['run_validity']}（须 VALID）")
        if r["formal_score"] != 1:
            problems.append(f"oracle#{r['index']} formal_score={r['formal_score']}（须 1）")
        if r["failed"] != 0:
            problems.append(f"oracle#{r['index']} failed={r['failed']}（须 0）")

    for r in nop:
        if "error" in r:
            problems.append(f"nop#{r['index']} 执行失败: {r['error']}")
            continue
        if r["run_validity"] != "VALID":
            problems.append(f"nop#{r['index']} run_validity={r['run_validity']}（须 VALID）")
        if r["formal_score"] != 0:
            problems.append(f"nop#{r['index']} formal_score={r['formal_score']}（须 0）")
        if r["invalid"] != 0:
            problems.append(f"nop#{r['index']} invalid={r['invalid']}（须 0）")
        if r["passed"] == 0:
            problems.append(f"nop#{r['index']} passed=0（须至少一个 P2P 通过）")

    # 版本一致性
    versions = {r.get("task_version") for r in rounds if "error" not in r}
    if versions != {"1.2.0"}:
        problems.append(f"task_version 不一致或非 1.2.0: {versions}")

    out = {
        "task_id": "wfflab__wreparse-217",
        "task_version": "1.2.0",
        "rounds": rounds,
        "gates": {
            "oracle_all_valid_score1": all(
                "error" not in r and r["run_validity"] == "VALID" and r["formal_score"] == 1 for r in oracle),
            "nop_all_valid_score0": all(
                "error" not in r and r["run_validity"] == "VALID" and r["formal_score"] == 0 for r in nop),
            "task_version_consistent": versions == {"1.2.0"},
        },
        "problems": problems,
    }
    out_path = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\controls_217_v120.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print()
    print(f"证据已写入: {out_path}")
    for k, v in out["gates"].items():
        print(f"  {k} = {v}")
    if problems:
        print("\n未通过：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n控制组门禁全部符合（Oracle 3×VALID/1，NOP 3×VALID/0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
