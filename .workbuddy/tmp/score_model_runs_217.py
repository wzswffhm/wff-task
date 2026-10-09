# -*- coding: utf-8 -*-
"""对 217 的模型候选补丁跑本机 L2 判分，回填 report.json / per_testcase.json。

背景：`run_model_validation.py` 只负责「调用模型 + 记录」，其产出的
`report.json.score` 恒为 `null`、`per_testcase.json` 为空，必须由判分层执行
F2P/P2P 后回填（见该脚本 `_note` 与 SKILL 说明）。

判分链路复用 `_qc_runs/tools/verify_controls_217.py` 已验证的本机路径：
    powershell -File tests/prepare.ps1 -TaskRoot <TASK>
    powershell -File tests/test.ps1    -TaskRoot <TASK>
    -> results/result.json（aggregate-v1：cases / run_validity / formal_score）

候选来源优先级：
    1) <run_dir>/patch.diff   （agent_harness 的 git diff，最规范）
    2) agent_harness 沙箱目录  （<sandbox>/WReparse，补丁缺失时回退）

用法：
    python score_model_runs_217.py --runs-dir <extras/model_runs> [--only qwen3.8-max] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-windows" / "wfflab__wreparse-217"
WORKSPACE = TASK / "environment" / "workspace"
TARGET = WORKSPACE / "WReparse"
PWSH = "powershell.exe"
BASELINE = REPO / "_qc_runs" / "baseline-217-v120" / "WReparse"


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    cmd = [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def save_baseline() -> None:
    if BASELINE.exists():
        return
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TARGET, BASELINE)


def restore_baseline() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(BASELINE, TARGET)


def apply_candidate(run_dir: Path, meta: dict) -> tuple[bool, str]:
    """把模型候选写入 workspace/WReparse。"""
    patch = run_dir / "patch.diff"
    if patch.is_file() and patch.stat().st_size > 0:
        # 补丁相对沙箱根（含 WReparse/... 层级）→ 在 workspace 下应用
        for strip in ("-p1", "-p2", "-p0"):
            p = subprocess.run(["git", "apply", "--binary", strip, "--whitespace=nowarn", str(patch)],
                               cwd=str(WORKSPACE), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if p.returncode == 0:
                return True, f"git apply {strip}"
        # 全部失败 -> 回退沙箱
    sb = meta.get("sandbox")
    if sb and (Path(sb) / "WReparse").is_dir():
        if TARGET.exists():
            shutil.rmtree(TARGET)
        shutil.copytree(Path(sb) / "WReparse", TARGET)
        return True, f"沙箱复制 {sb}\\WReparse"
    return False, "无可用候选（补丁缺失且沙箱不存在）"


def score_one(run_dir: Path) -> dict:
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}

    restore_baseline()
    ok, how = apply_candidate(run_dir, meta)
    if not ok:
        return {"status": "INVALID", "reason": how}

    # 构建夹具 + 判分（与控制组同链路）
    run_ps(TASK / "tests" / "prepare.ps1", "-TaskRoot", str(TASK))
    code, out = run_ps(TASK / "tests" / "test.ps1", "-TaskRoot", str(TASK))

    rp = TASK / "results" / "result.json"
    if not rp.is_file():
        return {"status": "INVALID", "reason": "results/result.json 缺失", "how": how}
    doc = json.loads(rp.read_text(encoding="utf-8-sig"))
    cases = doc.get("cases") or []

    report = {
        "task_id": doc.get("task_id"),
        "task_version": doc.get("task_version"),
        "run_index": meta.get("run_index"),
        "model_dir": meta.get("model_dir"),
        "status": doc.get("run_validity"),
        "score": doc.get("formal_score"),
        "verdict": doc.get("verdict"),
        "criteria_counted": doc.get("total"),
        "passed": doc.get("passed"),
        "failed": doc.get("failed"),
        "invalid": doc.get("invalid"),
        "test_exit": code,
        "candidate_applied_by": how,
        "report_status": doc.get("report_status") or (doc.get("test") or {}).get("report", {}).get("status"),
        "_note": "由 score_model_runs_217.py 在本机真实 Windows PowerShell 5.1 判分后回填",
    }
    per_tc = {
        "task_id": doc.get("task_id"),
        "run_index": meta.get("run_index"),
        "_note": "本机 L2 判分逐条结果（test.ps1 -> aggregate-v1 cases）",
        "results": {c.get("test_id"): ("PASS" if c.get("passed") else "FAIL") for c in cases},
    }
    return {"status": report["status"], "score": report["score"], "report": report,
            "per_testcase": per_tc, "how": how,
            "passed": report["passed"], "total": report["criteria_counted"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, help="extras/model_runs 目录")
    ap.add_argument("--only", default="", help="只判指定模型目录名（逗号分隔）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    runs_root = Path(args.runs_dir)
    if not runs_root.is_dir():
        print(f"目录不存在: {runs_root}")
        return 2
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    save_baseline()
    print(f"候选基线已备份: {BASELINE}")

    summary = {}
    for model_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        if only and model_dir.name not in only:
            continue
        for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            if not (run_dir / "meta.json").is_file():
                continue
            if args.dry_run:
                print(f"  [dry-run] {model_dir.name}/{run_dir.name}")
                continue
            r = score_one(run_dir)
            if "report" in r:
                (run_dir / "report.json").write_text(
                    json.dumps(r["report"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                (run_dir / "per_testcase.json").write_text(
                    json.dumps(r["per_testcase"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"  {model_dir.name:20} {run_dir.name}: status={r['status']} "
                  f"score={r.get('score')} ({r.get('passed')}/{r.get('total')}) via {r.get('how','')}")
            summary[f"{model_dir.name}/{run_dir.name}"] = r.get("report") or {"status": r["status"], "reason": r.get("reason")}

    restore_baseline()
    print(f"\n候选基线已复原")
    (REPO / "_qc_runs" / "score_model_runs_217_v120.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"汇总已写入: _qc_runs/score_model_runs_217_v120.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
