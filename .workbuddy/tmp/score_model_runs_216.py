# -*- coding: utf-8 -*-
"""wchunk-216 模型候选判分器：隔离副本上应用补丁 -> 跑 test.ps1 -> 回填报告。

复用 score_model_runs_217_iso2.py 的全部教训：
  * 副本绑定 task_version，不一致即重建（避免拿旧判据判新卷）；
  * 只判 agent status == VALID 的场次（INVALID 无候选，判了也是基线分，会污染 --score-only）；
  * 题包本体全程只读，判分发生在 tempfile 副本上，可与并发 agent 共存；
  * 优先 git apply 补丁，失败回退沙箱复制。

产出：
  <run>/report.json        逐项汇总（score / passed / failed / rubric 未满足项）
  <run>/per_testcase.json  18 条 test_id -> PASS/FAIL

用法：
  python score_model_runs_216.py --runs-dir <extras/model_runs> [--only qwen3.8-max]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_SRC = REPO / "harbor-windows" / "wfflab__wchunk-216"
PWSH = "powershell.exe"


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def task_version(path: Path) -> str:
    try:
        text = (path / "tests" / "run_tests.ps1").read_text(encoding="utf-8")
        m = re.search(r"task_version\s*=\s*'([^']+)'", text)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def ensure_stage(stage: Path) -> None:
    """副本存在但 task_version 与题包不一致时强制重建。"""
    src_v = task_version(TASK_SRC)
    box_v = task_version(stage) if stage.is_dir() else "missing"
    if stage.is_dir() and src_v == box_v:
        return
    if stage.is_dir():
        print(f"[重建] 副本 task_version={box_v} != 题包 {src_v}")
        shutil.rmtree(stage)
    shutil.copytree(TASK_SRC, stage,
                    ignore=shutil.ignore_patterns("jobs", "results", "_rejudge"))
    print(f"[重建] 判分副本已按题包刷新: {task_version(stage)}")


def apply_candidate(stage: Path, run_dir: Path, meta: dict) -> tuple[bool, str]:
    workspace = stage / "environment" / "workspace"
    patch = run_dir / "patch.diff"
    if patch.is_file() and patch.stat().st_size > 0:
        for strip in ("-p1", "-p2", "-p0"):
            p = subprocess.run(["git", "apply", "--binary", strip, "--whitespace=nowarn", str(patch)],
                               cwd=str(workspace), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            if p.returncode == 0:
                return True, f"git apply {strip}"
    sandbox = meta.get("sandbox")
    if sandbox and (Path(sandbox) / "wchunk").is_dir():
        target = workspace / "wchunk"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(Path(sandbox) / "wchunk", target)
        return True, "沙箱复制"
    return False, "无可用候选（补丁缺失且沙箱不存在）"


def score_one(stage: Path, run_dir: Path) -> dict:
    meta_path = run_dir / "meta.json"
    if not meta_path.is_file():
        return {"status": "SKIP", "reason": "无 meta.json"}
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("status") != "VALID":
        return {"status": "SKIP", "reason": f"agent status={meta.get('status')}（无有效候选）"}

    # 每轮重置：清 results + 恢复候选基线
    results = stage / "results"
    if results.exists():
        shutil.rmtree(results)
    shutil.copytree(TASK_SRC / "environment" / "workspace" / "wchunk",
                    stage / "environment" / "workspace" / "wchunk",
                    dirs_exist_ok=True)

    ok, how = apply_candidate(stage, run_dir, meta)
    if not ok:
        return {"status": "INVALID", "reason": how}

    run_ps(stage / "environment" / "prepare.ps1", "-TaskRoot", str(stage))
    code, out = run_ps(stage / "tests" / "test.ps1", "-TaskRoot", str(stage))

    checks_path = results / "checks.json"
    if not checks_path.is_file():
        return {"status": "INVALID", "reason": "results/checks.json 缺失", "how": how,
                "tail": out[-400:]}

    doc = json.loads(checks_path.read_text(encoding="utf-8-sig"))
    checks = doc.get("checks") or []
    failed = [c for c in checks if c.get("status") != "PASS"]
    passed = len(checks) - len(failed)

    # aggregate 产物（存在则取其 score/rubric，缺失则由 checks 推导）
    agg = read_json(results / "result.json") or {}
    score = agg.get("score")
    if score is None:
        score = 1 if passed == len(checks) and checks else 0

    report = {
        "task_id": doc.get("task_id"),
        "task_version": doc.get("task_version"),
        "run_index": meta.get("run_index"),
        "model_dir": meta.get("model_dir"),
        "status": "VALID" if code != 2 else "INVALID",
        "score": score,
        "weighted": agg.get("weighted"),
        "unsatisfied_rubric_items": agg.get("unsatisfied_rubric_items"),
        "criteria_counted": len(checks),
        "passed": passed,
        "failed": len(failed),
        "failed_ids": [c.get("test_id") for c in failed],
        "test_exit": code,
        "candidate_applied_by": how,
        "_note": "score_model_runs_216.py 在题包私有副本上判分（原题包只读）",
    }
    per_tc = {
        "task_id": doc.get("task_id"),
        "run_index": meta.get("run_index"),
        "_note": "本机 L2 判分逐条结果（隔离副本 + tests/test.ps1）",
        "results": {c.get("test_id"): c.get("status") for c in checks},
    }
    return {"report": report, "per_testcase": per_tc}


def read_json(path: Path):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--stage", default="", help="自定义判分副本目录（默认 temp 下创建）")
    args = ap.parse_args()

    runs_root = Path(args.runs_dir)
    if not runs_root.is_dir():
        print(f"目录不存在: {runs_root}")
        return 2
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    stage = Path(args.stage) if args.stage else Path(tempfile.mkdtemp(prefix="wchunk216-judge-"))
    print(f"判分副本: {stage}")
    ensure_stage(stage)

    out = {}
    try:
        for model_dir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
            if only and model_dir.name not in only:
                continue
            for run_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
                r = score_one(stage, run_dir)
                if "report" in r:
                    rep = r["report"]
                    (run_dir / "report.json").write_text(
                        json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                    (run_dir / "per_testcase.json").write_text(
                        json.dumps(r["per_testcase"], ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
                    print(f"  {model_dir.name:20} {run_dir.name}: score={rep['score']} "
                          f"({rep['passed']}/{rep['criteria_counted']}) "
                          f"unsat={rep.get('unsatisfied_rubric_items')} via {rep['candidate_applied_by']}")
                    out[f"{model_dir.name}/{run_dir.name}"] = rep
                else:
                    print(f"  {model_dir.name:20} {run_dir.name}: {r.get('status')} ({r.get('reason')})")
                    out[f"{model_dir.name}/{run_dir.name}"] = r
    finally:
        if not args.stage:
            shutil.rmtree(stage, ignore_errors=True)

    dest = REPO / "_qc_runs" / "score_model_runs_216.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n汇总: {dest}")
    print("（原题包只读；SKIP 的是 agent INVALID 场次，不计入 --score-only）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
