# -*- coding: utf-8 -*-
"""score_model_runs.py —— 对 harbor-windows 各次模型运行执行 L2 判分并回填分数

## 定位

`run_model_validation.py` 只负责**调用模型并收集补丁**（模型调用层）；真正的
F2P/P2P 二值判分由判分层完成。本脚本是两者之间的**回填器**：

    遍历 <task>/extras/model_runs/<model_dir>/run-N/patch.diff
      → 交给 l2_runner 在真实 Windows Runtime 中判分
      → 回填该 run 的 report.json（score / 判分证据指针）
      → 回填 per_testcase.json（逐 required 用例 PASS/FAIL/EVIDENCE_MISSING）

判分证据（reward.txt / reward.json / reward-details.json / report.json）留在
`run-N/judge/` 下，与 0001 批次同构，便于复核。

## 用法

    # 判分全部「已有补丁但尚未回填 score」的运行
    python score_model_runs.py --task ../../harbor-windows/wfflab__wsync-142

    # 只判指定模型 / 指定轮次
    python score_model_runs.py --task <task> --models opus-5 --runs 2,3

    # 强制全部重判
    python score_model_runs.py --task <task> --force

## 退出码

    0  全部判分成功（VALID）
    1  存在判分失败（INVALID）—— 须查明原因
    2  参数错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l2_runner  # noqa: E402


# ------------------------------------------------------------------ 工具

def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def flatten_verifier_report(vr: dict) -> dict:
    """把 grade.py 的 report.json 展平成 {testcase_name: PASS|FAIL|EVIDENCE_MISSING}。"""
    out = {}
    for group in ("FAIL_TO_PASS", "PASS_TO_PASS"):
        g = vr.get(group) or {}
        for t in g.get("success") or []:
            out[t] = "PASS"
        for t in g.get("failure") or []:
            out[t] = "FAIL"
        for t in g.get("other") or []:
            out[t] = "OTHER"          # SKIP / ERROR —— 证据不完整
        # missing 只有名字命中失败时才有值，此时名字可能与 spec 里的写法不同，
        # 故不能直接当 per_testcase 的键；由 spec 侧补 EVIDENCE_MISSING。
    return out


def backfill(task_dir: Path, run_dir: Path, case: str, judge_root: Path,
             summ: dict, elapsed: float) -> None:
    tid = task_dir.name
    rep_p = run_dir / "report.json"
    rep = read_json(rep_p, {}) or {}
    pt_p = run_dir / "per_testcase.json"
    pt = read_json(pt_p, {}) or {}

    spec = read_json(task_dir / "tests" / "swelive_spec.json", {}) or {}
    verifier_dir = judge_root / (case + "__verifier")
    vr = read_json(verifier_dir / "report.json", {}) or {}
    per = flatten_verifier_report(vr)

    if summ.get("status") == "VALID":
        # ---------- report.json ----------
        rep.update({
            "task_id": tid,
            "run_index": rep.get("run_index"),
            "status": "VALID",
            "score": summ.get("score"),
            "judge": {
                "engine": "l2_runner.py (本机真实 Windows Runtime，复现 tests/test.ps1)",
                "pytest_rc": summ.get("pytest_rc"),
                "grade_rc": summ.get("grade_rc"),
                "pytest_passed": summ.get("pytest_passed"),
                "pytest_total": summ.get("pytest_total"),
                "f2p_all_pass": summ.get("f2p_all_pass"),
                "p2p_all_pass": summ.get("p2p_all_pass"),
                "infrastructure_valid": summ.get("infrastructure_valid"),
                "candidate_failure": summ.get("candidate_failure"),
                "evidence_dir": str(verifier_dir.relative_to(task_dir)).replace("\\", "/"),
                "elapsed_sec": summ.get("elapsed"),
                "scored_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        })
        rep.pop("_note", None)

        # ---------- per_testcase.json ----------
        results = {}
        for t in spec.get("FAIL_TO_PASS", []):
            results[t] = per.get(t, "EVIDENCE_MISSING")
        for t in spec.get("PASS_TO_PASS", []):
            results[t] = per.get(t, "EVIDENCE_MISSING")
        pt.update({
            "task_id": tid,
            "run_index": rep.get("run_index"),
            "source": "grade.py report.json（二值：required F2P + required P2P 全过 = 1）",
            "results": results,
            "f2p_all_pass": summ.get("f2p_all_pass"),
            "p2p_all_pass": summ.get("p2p_all_pass"),
        })
        pt.pop("_note", None)
    else:
        # 判分本身失败 → 该 run 的分数不可信，必须置为 INVALID 而不是 0 分
        rep.update({
            "status": "INVALID",
            "score": None,
            "judge": {
                "engine": "l2_runner.py",
                "invalid_reason": summ.get("invalid_reason"),
                "elapsed_sec": summ.get("elapsed"),
            },
            "score_note": ("判分链路未产出可信 reward 产物，按契约不得记为 0 分；"
                           "须修因后重判"),
        })
        rep.pop("_note", None)

    # 单次运行只记录自己的 score；model_score_sum 是模型级汇总，由
    # run_model_validation.py --score-only 计算，不应落在 run 级报告里。
    rep.pop("model_score_sum", None)
    write_json(rep_p, rep)
    write_json(pt_p, pt)
    write_json(run_dir / "judge" / (case + ".summary.json"), summ)


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser(description="model_runs 补丁 → L2 判分 → 回填分数")
    ap.add_argument("--task", required=True, help="题包目录")
    ap.add_argument("--models", help="只判这些模型目录（逗号分隔），默认全部")
    ap.add_argument("--runs", help="只判这些轮次（逗号分隔，1-based），默认全部")
    ap.add_argument("--force", action="store_true", help="已回填的也重判")
    ap.add_argument("--out", help="判分沙箱根目录（默认 <task>/extras/model_runs/_judge）")
    a = ap.parse_args()

    task_dir = Path(a.task).resolve()
    if not (task_dir / "task.toml").is_file():
        print(f"错误: {task_dir} 不是题包目录（缺 task.toml）", file=sys.stderr)
        return 2

    runs_root = task_dir / "extras" / "model_runs"
    if not runs_root.is_dir():
        print(f"错误: 未找到 {runs_root}", file=sys.stderr)
        return 2

    judge_root = Path(a.out).resolve() if a.out else (runs_root / "_judge")
    judge_root.mkdir(parents=True, exist_ok=True)

    want_models = set(x.strip() for x in a.models.split(",")) if a.models else None
    want_runs = set(int(x) for x in a.runs.split(",")) if a.runs else None

    todo = []
    for mdir in sorted(p for p in runs_root.iterdir() if p.is_dir() and p.name != "_judge"):
        if want_models and mdir.name not in want_models:
            continue
        for rdir in sorted(mdir.glob("run-*")):
            try:
                n = int(rdir.name.split("-")[1])
            except (IndexError, ValueError):
                continue
            if want_runs and n not in want_runs:
                continue
            meta = read_json(rdir / "meta.json", {}) or {}
            rep = read_json(rdir / "report.json", {}) or {}
            patch = rdir / "patch.diff"
            if not patch.is_file():
                print(f"  [skip] {mdir.name}/{rdir.name}: 无 patch.diff"
                      f"（{meta.get('invalid_reason') or meta.get('status')}）")
                continue
            if not a.force and isinstance(rep.get("score"), (int, float)):
                print(f"  [skip] {mdir.name}/{rdir.name}: 已回填 score={rep['score']}"
                      f"（--force 可重判）")
                continue
            todo.append((mdir.name, n, rdir, patch))

    if not todo:
        print("没有需要判分的运行。")
        return 0

    print("=" * 66)
    print(f"待判分 {len(todo)} 次运行（判分沙箱：{judge_root}）")
    print("=" * 66)

    bad = 0
    for mname, n, rdir, patch in todo:
        case = "%s_r%d" % (mname.replace(".", "").replace("-", "_"), n)
        t0 = time.time()
        try:
            summ = l2_runner.run_case(task_dir, case, patch, judge_root)
        except Exception as e:
            summ = {"case": case, "status": "INVALID", "score": None,
                    "invalid_reason": "judge_exception: %s: %s" % (type(e).__name__, e)}
        summ["elapsed"] = round(time.time() - t0, 2)
        summ["candidate"] = f"{mname}/run-{n}"
        backfill(task_dir, rdir, case, judge_root, summ, summ["elapsed"])

        if summ.get("status") == "VALID":
            print(f"  [{mname}/run-{n}] VALID score={summ.get('score')} "
                  f"pytest={summ.get('pytest_passed')}/{summ.get('pytest_total')} "
                  f"F2P={summ.get('f2p_all_pass')} P2P={summ.get('p2p_all_pass')} "
                  f"({summ['elapsed']}s)")
        else:
            bad += 1
            print(f"  [{mname}/run-{n}] INVALID — {summ.get('invalid_reason')} "
                  f"({summ['elapsed']}s)")

    print("=" * 66)
    print(f"完成：成功={len(todo) - bad}  失败={bad}")
    if bad:
        print("失败项须查明原因后重判；判分失败不得记为该 run 的 0 分。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
