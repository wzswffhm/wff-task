# -*- coding: utf-8 -*-
"""score_model_runs_217.py 的**隔离版**：在 TASK 的私有副本上判分。

为什么需要：原版会临时改写
    harbor-windows/wfflab__wreparse-217/environment/workspace/WReparse
判分完再复原。但此刻仍有并发 job 在跑 agent，`agent_harness` 每轮都从
`environment/workspace` 复制沙箱 —— 万一新 run 恰好落在判分窗口内，就会复制到
「半应用的候选代码」，造成该 run 的产物不可信（且要重跑 55 分钟）。

本版把整个题包整树复制到 `_qc_runs/judge-sandbox-217/task`（排除 results/_rejudge），
所有 prepare/test 与候选写入都发生在副本内，原题包**全程只读**，因此可与并发
agent 完全共存，也可安全地多次调用。

用法：
    python score_model_runs_217_iso.py --runs-dir <extras/model_runs> [--only kimi-k3]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_SRC = REPO / "harbor-windows" / "wfflab__wreparse-217"
SANDBOX_ROOT = REPO / "_qc_runs" / "judge-sandbox-217"
TASK = SANDBOX_ROOT / "task"
TARGET = TASK / "environment" / "workspace" / "WReparse"
BASELINE = SANDBOX_ROOT / "baseline-WReparse"
PWSH = "powershell.exe"


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ensure_sandbox() -> None:
    """首次创建题包副本与候选基线；之后复用。"""
    if not TASK.is_dir():
        SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)
        shutil.copytree(TASK_SRC, TASK,
                        ignore=shutil.ignore_patterns("results", "_rejudge", "__pycache__"))
        print(f"已创建判分副本: {TASK}")
    if not BASELINE.is_dir():
        shutil.copytree(TARGET, BASELINE)
        print(f"已保存候选基线: {BASELINE}")


def restore_baseline() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(BASELINE, TARGET)


def apply_candidate(run_dir: Path, meta: dict) -> tuple[bool, str]:
    patch = run_dir / "patch.diff"
    if patch.is_file() and patch.stat().st_size > 0:
        for strip in ("-p1", "-p2", "-p0"):
            p = subprocess.run(["git", "apply", "--binary", strip, "--whitespace=nowarn", str(patch)],
                               cwd=str(TASK / "environment" / "workspace"),
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            if p.returncode == 0:
                return True, f"git apply {strip}"
    sb = meta.get("sandbox")
    if sb and (Path(sb) / "WReparse").is_dir():
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(Path(sb) / "WReparse", TARGET)
        return True, "沙箱复制"
    return False, "无可用候选"


def score_one(run_dir: Path) -> dict:
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    restore_baseline()
    ok, how = apply_candidate(run_dir, meta)
    if not ok:
        return {"status": "INVALID", "reason": how}

    run_ps(TASK / "tests" / "prepare.ps1", "-TaskRoot", str(TASK))
    code, _out = run_ps(TASK / "tests" / "test.ps1", "-TaskRoot", str(TASK))

    rp = TASK / "results" / "result.json"
    if not rp.is_file():
        return {"status": "INVALID", "reason": "results/result.json 缺失", "how": how}
    doc = json.loads(rp.read_text(encoding="utf-8-sig"))
    cases = doc.get("cases") or []
    report = {
        "task_id": doc.get("task_id"), "task_version": doc.get("task_version"),
        "run_index": meta.get("run_index"), "model_dir": meta.get("model_dir"),
        "status": doc.get("run_validity"), "score": doc.get("formal_score"),
        "verdict": doc.get("verdict"), "criteria_counted": doc.get("total"),
        "passed": doc.get("passed"), "failed": doc.get("failed"), "invalid": doc.get("invalid"),
        "test_exit": code, "candidate_applied_by": how,
        "_note": "由 score_model_runs_217_iso.py 在题包私有副本上判分后回填（原题包只读）",
    }
    per_tc = {"task_id": doc.get("task_id"), "run_index": meta.get("run_index"),
              "_note": "本机 L2 判分逐条结果（隔离沙箱）",
              "results": {c.get("test_id"): ("PASS" if c.get("passed") else "FAIL") for c in cases}}
    return {"report": report, "per_testcase": per_tc}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    runs_root = Path(args.runs_dir)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    ensure_sandbox()
    out = {}
    for model_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        if only and model_dir.name not in only:
            continue
        for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            if not (run_dir / "meta.json").is_file():
                continue
            r = score_one(run_dir)
            if "report" in r:
                (run_dir / "report.json").write_text(
                    json.dumps(r["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                (run_dir / "per_testcase.json").write_text(
                    json.dumps(r["per_testcase"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                rep = r["report"]
                print(f"  {model_dir.name:20} {run_dir.name}: status={rep['status']} "
                      f"score={rep['score']} ({rep['passed']}/{rep['criteria_counted']}) "
                      f"via {rep['candidate_applied_by']}")
                out[f"{model_dir.name}/{run_dir.name}"] = rep
            else:
                print(f"  {model_dir.name:20} {run_dir.name}: INVALID ({r.get('reason')})")
                out[f"{model_dir.name}/{run_dir.name}"] = r
    restore_baseline()
    (REPO / "_qc_runs" / "score_iso_217.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n汇总: _qc_runs/score_iso_217.json（原题包未被改写）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
