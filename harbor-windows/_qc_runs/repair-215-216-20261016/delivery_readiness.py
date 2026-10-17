# -*- coding: utf-8 -*-
"""delivery_readiness.py —— 215/216 v1.0.1 交付前一次性验收。

把甲方 QC 会做的**全部自动检查**在昂贵的 run_delivery_qc.py 之前跑一遍，
让缺件在"跑分刚结束"就暴露，而不是在打包/上传之后。

只读：不修改题包任何字节（改动会作废 12 个 job 的 task_checksum）。

用法：
    python delivery_readiness.py [--json out.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
QC_SCRIPTS = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC_SCRIPTS))

from inspect_delivery import inspect_delivery          # noqa: E402
from validate_model_jobs import validate_jobs          # noqa: E402
from validate_model_gate import REQUIRED_COUNTS        # noqa: E402

PKGS = [
    ("215", ROOT / "harbor-windows" / "wfflab__wsparse-215-v1.0.1-delivery",
     "ghcr.io/wzswffhm/wfflab-windows:wsparse-215-1.0.1"),
    ("216", ROOT / "harbor-windows" / "wfflab__wvas-216-v1.0.1-delivery",
     "ghcr.io/wzswffhm/wfflab-windows:wvas-216-1.0.1"),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def static_checks(pkg: Path, expected_image: str) -> tuple[list[str], list[str], dict]:
    """返回 (errors, warnings, facts)。"""
    errors: list[str] = []
    warnings: list[str] = []
    facts: dict = {}

    for name in ("task.toml", "instruction.md", "environment", "solution", "tests"):
        if not (pkg / name).exists():
            errors.append(f"缺少根目录项: {name}")

    toml_text = ""
    tp = pkg / "task.toml"
    if tp.is_file():
        toml_text = tp.read_text(encoding="utf-8-sig", errors="replace")
        for field in ("version", "task_type", "docker_image", "knowledge_tree", "authors"):
            if field not in toml_text:
                errors.append(f"task.toml 缺少字段: {field}")
        if "latest" in toml_text.lower():
            warnings.append("task.toml 出现 'latest' 字样，需人工确认不是浮动 tag")
        m = None
        for line in toml_text.splitlines():
            s = line.strip()
            if s.startswith("docker_image") and "=" in s:
                m = s.split("=", 1)[1].strip().strip('"').strip("'")
                break
        facts["docker_image"] = m
        if m and m != expected_image:
            errors.append(f"docker_image 与期望不一致: {m} != {expected_image}")

    for junk in pkg.rglob("*.bak"):
        errors.append(f"残留备份文件: {junk.relative_to(pkg)}")

    rq = read_json(pkg / "tests" / "required_testcases.json")
    rows = rq.get("testcases") if isinstance(rq, dict) else rq
    ids, groups = [], {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                ids.append(row["id"])
                groups[row["id"]] = str(row.get("group") or "").upper()
    facts["required_count"] = len(ids)
    facts["f2p"] = sum(1 for g in groups.values() if g == "F2P")
    facts["p2p"] = sum(1 for g in groups.values() if g == "P2P")
    if len(ids) < 5:
        errors.append(f"required_testcases 少于 5 条: {len(ids)}")
    if not facts["f2p"]:
        errors.append("required_testcases 没有 F2P")
    if not facts["p2p"]:
        errors.append("required_testcases 没有 P2P")
    if len(set(ids)) != len(ids):
        errors.append("required_testcases 有重复 id")

    judge = pkg / "tests" / "judge.toml"
    rubric = pkg / "tests" / "rubric.json"
    if judge.is_file() and rubric.is_file():
        declared = None
        for line in judge.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("source_sha256") and "=" in s:
                declared = s.split("=", 1)[1].strip().strip('"').strip("'")
                break
        actual = sha256_file(rubric)
        facts["judge_source_sha256"] = declared
        facts["rubric_sha256"] = actual
        if declared != actual:
            errors.append("judge.toml:source_sha256 与 rubric.json 实际 sha256 不一致")

    facts["has_jobs_dir"] = (pkg / "jobs").is_dir()
    return errors, warnings, facts


def model_gap(report: dict) -> dict:
    """从 validate_jobs 的 evidence 里算 Qwen/Opus 总分与分差。"""
    ev = report.get("evidence") or {}
    models = ev.get("models") or {}
    sums = {}
    for alias in REQUIRED_COUNTS:
        runs = models.get(alias) or []
        sums[alias] = sum(int(r.get("score") or 0) for r in runs)
    q, o = sums.get("qwen", 0), sums.get("opus", 0)
    return {
        "qwen_sum": q, "opus_sum": o,
        "strict_gap_ok": q < o,
        "all_qwen_full": q == REQUIRED_COUNTS["qwen"],
        "all_opus_full": o == REQUIRED_COUNTS["opus"],
        "note": ("双满，按新口径必须 FAIL" if q == 3 and o == 3
                 else "分差成立" if q < o else "分差不成立"),
    }


def check_package(label: str, pkg: Path, image: str) -> dict:
    result = {"label": label, "package": str(pkg), "errors": [], "warnings": []}
    if not pkg.is_dir():
        result["errors"].append(f"题包不存在: {pkg}")
        result["ready"] = False
        return result

    errors, warnings, facts = static_checks(pkg, image)
    result["errors"] += errors
    result["warnings"] += warnings
    result["static"] = facts

    try:
        layout = inspect_delivery(pkg)
        result["layout_pass"] = bool(layout.get("pass"))
        if not layout.get("pass"):
            result["errors"] += [f"交付目录: {e}" for e in (layout.get("errors") or [])]
        result["layout"] = {k: v for k, v in layout.items() if k in ("pass", "errors", "warnings")}
    except Exception as exc:
        result["errors"].append(f"inspect_delivery 失败: {type(exc).__name__}: {exc}")
        result["layout_pass"] = False

    jobs = pkg / "jobs"
    if not jobs.is_dir():
        result["jobs"] = {"present": False,
                          "note": "jobs/ 尚未组装（跑分或 assemble 未完成）"}
        result["ready"] = False
        return result

    identity = {
        "task_id": f"wfflab__{label}",
        "task_version": "1.0.1",
        "task_hash": facts.get("rubric_sha256"),
        "harbor_task_checksum": None,
    }
    try:
        vr = validate_jobs(jobs, pkg, identity)
        result["jobs"] = {
            "present": True,
            "pass": bool(vr.get("pass")),
            "errors": vr.get("errors") or [],
            "warnings": vr.get("warnings") or [],
            "discovered_counts": vr.get("discovered_counts") or {},
            "harbor_task_checksums": vr.get("harbor_task_checksums") or [],
            "gate": model_gap(vr),
        }
        # 分差不成立/双满属硬门禁，必须计入 blocking，不能被 validate_jobs 的 pass 掩盖。
        _gate = result["jobs"]["gate"]
        _counts = result["jobs"]["discovered_counts"] or {}
        if _counts.get("qwen") and _counts.get("opus"):
            if not _gate["strict_gap_ok"]:
                result["errors"].append(
                    "模型分差不成立: Qwen=%s Opus=%s（要求严格 Qwen < Opus；相等或反向均 FAIL）"
                    % (_gate["qwen_sum"], _gate["opus_sum"]))
            if _gate.get("all_qwen_full") and _gate.get("all_opus_full"):
                result["errors"].append("Qwen 与 Opus 三轮全满分，按甲方口径必须 FAIL（题目过易）")
        result["errors"] += [f"jobs: {e}" for e in (vr.get("errors") or [])]
        result["warnings"] += [f"jobs: {w}" for w in (vr.get("warnings") or [])]
        if len(vr.get("harbor_task_checksums") or []) > 1:
            result["errors"].append("12 个 job 的 task_checksum 不一致")
    except Exception as exc:
        result["errors"].append(f"validate_jobs 失败: {type(exc).__name__}: {exc}")
        result["jobs"] = {"present": True, "pass": False}

    result["ready"] = not result["errors"]
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    reports = [check_package(label, pkg, image) for label, pkg, image in PKGS]

    print("=" * 78)
    print("215/216 v1.0.1 交付就绪验收")
    print("=" * 78)
    for r in reports:
        print(f"\n--- [{r['label']}] {'READY' if r.get('ready') else 'NOT READY'} ---")
        st = r.get("static") or {}
        if st:
            print(f"  镜像引用     : {st.get('docker_image')}")
            print(f"  required     : {st.get('required_count')} 条 (F2P {st.get('f2p')} / P2P {st.get('p2p')})")
            print(f"  judge hash   : {'OK' if st.get('judge_source_sha256') == st.get('rubric_sha256') else 'MISMATCH'}")
            print(f"  jobs/ 存在   : {st.get('has_jobs_dir')}")
        print(f"  交付目录检查 : {'PASS' if r.get('layout_pass') else 'FAIL'}")
        j = r.get("jobs") or {}
        if j.get("present"):
            print(f"  jobs 校验    : {'PASS' if j.get('pass') else 'FAIL'}")
            print(f"  各类数量     : {j.get('discovered_counts')}")
            g = j.get("gate") or {}
            if g:
                print(f"  分差         : Qwen={g.get('qwen_sum')} Opus={g.get('opus_sum')} "
                      f"-> {'成立' if g.get('strict_gap_ok') else '不成立'} ({g.get('note')})")
            print(f"  checksums    : {j.get('harbor_task_checksums')}")
        else:
            print(f"  jobs 校验    : {j.get('note', 'missing')}")
        if r["errors"]:
            print(f"  阻塞项 ({len(r['errors'])}):")
            for e in r["errors"][:40]:
                print(f"    - {e}")
        if r["warnings"]:
            print(f"  警告 ({len(r['warnings'])}):")
            for w in r["warnings"][:15]:
                print(f"    ~ {w}")

    print("\n" + "=" * 78)
    print("结论：" + ("两个包均 READY" if all(r.get("ready") for r in reports)
                     else "仍有阻塞项，见上"))
    print("=" * 78)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告 -> {args.json}")
    return 0 if all(r.get("ready") for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
