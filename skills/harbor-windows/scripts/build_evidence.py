#!/usr/bin/env python3
"""build_evidence.py —— 生成 harbor-windows 题包的对照证据目录

按《Windows 专项 Coding Bench 数据采购》(windwos-第二版) 第 7 章，单题交付前至少要有：

    extras/evidence/
      no_change/run-1..3/          base 上独立运行 3 次，正式分均为 0
      golden/run-1..3/             Golden 上独立运行 3 次，正式分均为 1
      clean_room/{no_change,golden}/   在全新目录里重建后复验
      negative_and_equivalent_controls/  反例与等价实现对照
      cleanup_and_restore/README.md      清理与恢复说明（本脚本不覆盖）

每个 run 目录与 0001 批次同构：
    pytest-results.json / pytest-stdout.txt / grade-stdout.txt / test.log
    summary.json
    verifier/{report.json,reward.txt,reward.json,reward-details.json}

判分统一走 ``l2_runner.run_case``（本机真实 Windows Runtime，复现 tests/test.ps1）。

用法：
    python build_evidence.py --task <题包目录>
    python build_evidence.py --task <题包目录> --runs 3
    python build_evidence.py --task <题包目录> --only no_change,golden
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l2_runner  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"

GIT = ["git", "-c", "core.autocrlf=false", "-c", "core.longpaths=true",
       "-c", "user.name=wfflab", "-c", "user.email=wfflab@local",
       "-c", "commit.gpgsign=false"]


def detect_module(base_workspace: Path) -> str:
    """从 ``environment/workspace/`` 推断被测包名（唯一含 __init__.py 的目录）。"""
    found = [p.name for p in sorted(base_workspace.iterdir())
             if p.is_dir() and p.name != "tests" and (p / "__init__.py").is_file()]
    if len(found) != 1:
        raise SystemExit("无法唯一确定被测包名（候选：%s）" % (found or "无"))
    return found[0]


def load_variants(module: str) -> dict:
    """变体清单优先读 ``assets/<module>-variants/manifest.json``。

    回退到仓库内置的 wsync 清单，保证旧题包仍可复跑。
    """
    manifest = ASSETS_DIR / ("%s-variants" % module) / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return {name: (info.get("desc", ""), info.get("expect"))
                for name, info in (data.get("variants") or {}).items()}
    if module == "wsync":
        return {
            "negative_01_readonly_only": (
                "反例：只做局部修补（清只读属性 + 路径大小写归一 + 单条目 try/except），"
                "不处理类型冲突、内容级判定与时间戳保真。", 0.0),
            "negative_02_swallow_errors": (
                "反例：把失败条目静默吞掉并计为成功，于是 sync_tree 表面永远“成功”。", 0.0),
            "negative_03_force_clean_target": (
                "反例：同步前直接清空目标目录以回避类型冲突，保留语义被破坏且不幂等。", 0.0),
            "equivalent_01_alternate_impl": (
                "等价实现：scandir 遍历 + sha256 比对 + 临时文件原子替换，结构不同、行为等价。", 1.0),
        }
    raise SystemExit("缺少变体清单：%s" % manifest)


def sh(args, cwd, timeout=1800):
    p = subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, p.stdout or "", p.stderr or ""


def make_variant_patch(base_workspace: Path, module: str, variant_name: str,
                       workdir: Path) -> Path:
    """把某个对照变体的源码打成可 git apply 的补丁。"""
    src = ASSETS_DIR / ("%s-variants" % module) / variant_name / module
    if not src.is_dir():
        raise SystemExit("缺少变体源码：%s" % src)
    scratch = workdir / ("patch-" + variant_name)
    if scratch.exists():
        shutil.rmtree(scratch, ignore_errors=True)
    shutil.copytree(base_workspace, scratch)
    sh(["git", "init", "-q"], scratch)
    sh(GIT + ["add", "-A"], scratch)
    sh(GIT + ["commit", "-q", "-m", "base"], scratch)
    for f in sorted(src.glob("*.py")):
        shutil.copy2(f, scratch / module / f.name)
    sh(GIT + ["add", "-A"], scratch)
    rc, out, err = sh(GIT + ["diff", "--cached", "--binary", "--no-color"], scratch)
    if rc != 0 or not out.strip():
        raise SystemExit("生成 %s 补丁失败：%s" % (variant_name, err[:300]))
    out_path = workdir / (variant_name + ".patch")
    out_path.write_text(out, encoding="utf-8", newline="\n")
    shutil.rmtree(scratch, ignore_errors=True)
    return out_path


def assemble(case_dir: Path, case: str, out_root: Path, summary: dict) -> None:
    """把 l2_runner 的产物整理成 evidence 目录的标准结构。"""
    case_dir.mkdir(parents=True, exist_ok=True)
    verifier_src = out_root / (case + "__verifier")
    if verifier_src.is_dir():
        shutil.copytree(verifier_src, case_dir / "verifier", dirs_exist_ok=True)

    for suffix, name in ((".pytest.log", "pytest-stdout.txt"),
                         (".grade.log", "grade-stdout.txt")):
        p = out_root / (case + suffix)
        (case_dir / name).write_text(p.read_text(encoding="utf-8", errors="replace")
                                     if p.is_file() else "", encoding="utf-8")

    report = summary.get("report") or {}
    f2p_failure = sorted((report.get("FAIL_TO_PASS") or {}).get("failure") or [])
    p2p_failure = sorted((report.get("PASS_TO_PASS") or {}).get("failure") or [])
    f2p_missing = sorted((report.get("FAIL_TO_PASS") or {}).get("missing") or [])
    p2p_missing = sorted((report.get("PASS_TO_PASS") or {}).get("missing") or [])

    evidence = {
        "group": case_dir.parent.name,
        "case": case,
        "judge_engine": "l2_runner.py（本机真实 Windows Runtime，复现 tests/test.ps1）",
        "status": summary.get("status"),
        "pytest_rc": summary.get("pytest_rc"),
        "grade_rc": summary.get("grade_rc"),
        "score": summary.get("score"),
        "pytest_passed": summary.get("pytest_passed"),
        "pytest_total": summary.get("pytest_total"),
        "f2p_all_pass": summary.get("f2p_all_pass"),
        "p2p_all_pass": summary.get("p2p_all_pass"),
        "f2p_failure": f2p_failure,
        "p2p_failure": p2p_failure,
        "f2p_missing": f2p_missing,
        "p2p_missing": p2p_missing,
        "infrastructure_valid": summary.get("infrastructure_valid"),
        "candidate_failure": summary.get("candidate_failure"),
        "invalid_reason": summary.get("invalid_reason"),
        "patch": summary.get("patch"),
        "seed": summary.get("seed"),
        "elapsed_sec": summary.get("elapsed"),
        "note": summary.get("note"),
    }
    (case_dir / "summary.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # pytest-results.json + test.log：与 test.ps1 链路一致的两份原料
    src_pr = out_root / case / "reports" / "pytest-results.json"
    if src_pr.is_file():
        text = src_pr.read_text(encoding="utf-8", errors="replace")
        (case_dir / "pytest-results.json").write_text(text, encoding="utf-8")
        (case_dir / "test.log").write_text(text, encoding="utf-8")


def run_one(task_dir: Path, case: str, patch: Path | None, out_root: Path,
            case_dir: Path, note: str | None = None) -> dict:
    t0 = time.time()
    summary = l2_runner.run_case(task_dir, case, patch, out_root)
    summary["elapsed"] = round(time.time() - t0, 2)
    summary["note"] = note
    assemble(case_dir, case, out_root, summary)
    return summary


def main():
    ap = argparse.ArgumentParser(description="生成 harbor-windows 题包对照证据")
    ap.add_argument("--task", required=True, help="题包目录")
    ap.add_argument("--runs", type=int, default=3, help="no_change / golden 各跑几次（默认 3）")
    ap.add_argument("--only", help="只做指定分组（逗号分隔：no_change,golden,clean_room,controls）")
    a = ap.parse_args()

    task_dir = Path(a.task).resolve()
    if not (task_dir / "task.toml").is_file():
        raise SystemExit("不是题包目录：%s" % task_dir)
    base_workspace = task_dir / "environment" / "workspace"
    oracle = task_dir / "solution" / "oracle.patch"
    ev_root = task_dir / "extras" / "evidence"
    module = detect_module(base_workspace)
    variants = load_variants(module)
    print("被测包：%s　变体数：%d" % (module, len(variants)))

    only = set(x.strip() for x in a.only.split(",")) if a.only else None

    workdir = Path(tempfile.mkdtemp(prefix="wff-evidence-"))
    out_root = workdir / "runs"
    out_root.mkdir(parents=True, exist_ok=True)

    results = []

    # ---------------- no_change / golden ----------------
    for group, patch in (("no_change", None), ("golden", oracle)):
        if only and group not in only:
            continue
        for n in range(1, a.runs + 1):
            case = "ev_%s_%d" % (group, n)
            print("[%s] run-%d ..." % (group, n), end=" ", flush=True)
            s = run_one(task_dir, case, patch, out_root, ev_root / group / ("run-%d" % n))
            results.append((group, s))
            print("status=%s score=%s (%.1fs)" % (s["status"], s["score"], s["elapsed"]))

    # ---------------- clean_room（全新目录重建后复验） ----------------
    if not only or "clean_room" in only:
        fresh = Path(tempfile.mkdtemp(prefix="wff-cleanroom-"))
        for group, patch in (("no_change", None), ("golden", oracle)):
            case = "cr_%s" % group
            print("[clean_room] %s ..." % group, end=" ", flush=True)
            s = run_one(task_dir, case, patch, fresh,
                        ev_root / "clean_room" / group,
                        note="全新目录重建后复验，评估环境恢复能力")
            results.append(("clean_room/" + group, s))
            print("status=%s score=%s (%.1fs)" % (s["status"], s["score"], s["elapsed"]))
        shutil.rmtree(fresh, ignore_errors=True)

    # ---------------- 反例与等价实现 ----------------
    if not only or "controls" in only:
        for name, (desc, expect) in variants.items():
            patch = make_variant_patch(base_workspace, module, name, workdir)
            case = "ctl_" + name
            print("[controls] %s ..." % name, end=" ", flush=True)
            s = run_one(task_dir, case, patch,
                        out_root, ev_root / "negative_and_equivalent_controls" / name,
                        note=desc)
            results.append((name, s))
            verdict = "符合预期" if s.get("score") == expect else "!! 与预期不符"
            print("status=%s score=%s 期望=%s %s (%.1fs)"
                  % (s["status"], s.get("score"), expect, verdict, s["elapsed"]))

    shutil.rmtree(workdir, ignore_errors=True)

    print("=" * 66)
    print("证据生成完成：")
    for name, s in results:
        print("  %-40s status=%-8s score=%-5s" % (name, s.get("status"), s.get("score")))

    bad = [n for n, s in results
           if s.get("status") != "VALID"
           or (n.startswith("negative") and s.get("score") != 0.0)
           or (n.startswith("equivalent") and s.get("score") != 1.0)
           or (n in ("no_change", "clean_room/no_change") and s.get("score") != 0.0)
           or (n in ("golden", "clean_room/golden") and s.get("score") != 1.0)]
    if bad:
        print("异常项：%s" % ", ".join(bad))
        return 1
    print("全部符合预期。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
