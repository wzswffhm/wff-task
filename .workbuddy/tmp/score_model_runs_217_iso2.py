# -*- coding: utf-8 -*-
"""在隔离副本上判分，**只处理已完成的 run**。

相比 score_model_runs_217_iso.py 的两处加固：
  ① meta.status 必须是 VALID/INVALID 才判 —— PENDING 表示 agent 还在跑，
     此时 patch.diff / 沙箱都未落盘，判分会拿到半成品（假分）。
  ② 副本式判分：整题包复制到 _qc_runs/judge-sandbox-217/task，
     不碰 harbor-windows/wfflab__wreparse-217，可与并发 agent 完全共存。

用法：python score_model_runs_217_iso2.py --runs-dir <extras/model_runs> [--only opus-5]
"""
from __future__ import annotations

import argparse
import json
import shutil
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_SRC = REPO / "harbor-windows" / "wfflab__wreparse-217"
SANDBOX = REPO / "_qc_runs" / "judge-sandbox-217"
TASK = SANDBOX / "task"
TARGET = TASK / "environment" / "workspace" / "WReparse"
BASELINE = SANDBOX / "baseline-WReparse"
PWSH = "powershell.exe"


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _task_version(task_dir: pathlib.Path) -> str:
    try:
        text = (task_dir / "tests" / "run_tests.ps1").read_text(encoding="utf-8")
        m = re.search(r"task_version\s*=\s*'([^']+)'", text)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def ensure_sandbox() -> None:
    """创建题包副本；当副本的 task_version 与题包不一致时**强制重建**
    task_version 与题包不一致，避免拿旧判据判新场次。"""
    src_v, box_v = _task_version(TASK_SRC), _task_version(TASK) if TASK.is_dir() else "missing"
    if TASK.is_dir() and src_v == box_v:
        if not BASELINE.is_dir():
            shutil.copytree(TARGET, BASELINE)
        return
    if TASK.is_dir():
        print(f"[重建] 副本 task_version={box_v} != 题包 {src_v}: {TASK}")
        shutil.rmtree(TASK)
    if BASELINE.is_dir():
        shutil.rmtree(BASELINE)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TASK_SRC, TASK,
                    ignore=shutil.ignore_patterns("results", "_rejudge", "__pycache__"))
    print(f"[重建] 判分副本已按题包刷新: {_task_version(TASK)}")
    shutil.copytree(TARGET, BASELINE)


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
    return False, "无可用候选（补丁缺失且沙箱不存在）"


def score_one(run_dir: Path) -> dict:
    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    restore_baseline()
    ok, how = apply_candidate(run_dir, meta)
    if not ok:
        return {"status": "INVALID", "reason": how}
    run_ps(TASK / "tests" / "prepare.ps1", "-TaskRoot", str(TASK))
    code, _ = run_ps(TASK / "tests" / "test.ps1", "-TaskRoot", str(TASK))
    rp = TASK / "results" / "result.json"
    if not rp.is_file():
        return {"status": "INVALID", "reason": "results/result.json 缺失"}
    doc = json.loads(rp.read_text(encoding="utf-8-sig"))
    cases = doc.get("cases") or []
    report = {
        "task_id": doc.get("task_id"), "task_version": doc.get("task_version"),
        "run_index": meta.get("run_index"), "model_dir": meta.get("model_dir"),
        "status": doc.get("run_validity"), "score": doc.get("formal_score"),
        "verdict": doc.get("verdict"), "criteria_counted": doc.get("total"),
        "passed": doc.get("passed"), "failed": doc.get("failed"), "invalid": doc.get("invalid"),
        "test_exit": code, "candidate_applied_by": how,
        "_note": "score_model_runs_217_iso2：隔离副本判分，原题包只读",
    }
    per_tc = {"task_id": doc.get("task_id"), "run_index": meta.get("run_index"),
              "_note": "本机 L2 判分逐条结果（隔离沙箱）",
              "results": {c.get("test_id"): ("PASS" if c.get("passed") else "FAIL") for c in cases}}
    return {"report": report, "per_testcase": per_tc}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--only", default="", help="模型目录名，逗号分隔")
    args = ap.parse_args()
    root = Path(args.runs_dir)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    ensure_sandbox()
    out = {}
    for model_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if only and model_dir.name not in only:
            continue
        for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            meta_path = run_dir / "meta.json"
            if not meta_path.is_file():
                print(f"  {model_dir.name:20} {run_dir.name}: 跳过（无 meta.json）")
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("status") != "VALID":
                print(f"  {model_dir.name:20} {run_dir.name}: 跳过（status={meta.get('status')}，未完成）")
                continue
            r = score_one(run_dir)
            if "report" in r:
                rep = r["report"]
                (run_dir / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8")
                (run_dir / "per_testcase.json").write_text(
                    json.dumps(r["per_testcase"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"  {model_dir.name:20} {run_dir.name}: status={rep['status']} "
                      f"score={rep['score']} ({rep['passed']}/{rep['criteria_counted']}) via {rep['candidate_applied_by']}")
                out[f"{model_dir.name}/{run_dir.name}"] = rep
            else:
                print(f"  {model_dir.name:20} {run_dir.name}: INVALID ({r.get('reason')})")
                out[f"{model_dir.name}/{run_dir.name}"] = r
    restore_baseline()
    (REPO / "_qc_runs" / "score_iso_217.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n汇总: _qc_runs/score_iso_217.json（原题包只读）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
