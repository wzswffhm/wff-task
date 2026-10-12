"""Run complete delivery QC: layout, eight model jobs, and real Oracle/NOP."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from inspect_delivery import inspect_delivery
from run_qc import check_archive_root_name, run as run_harbor_qc, safe_extract
from validate_model_gate import evaluate
from validate_model_jobs import validate_jobs


QUALITY_GATES = {
    "golden_nop_expected": "Golden/NOP 得分和逐 testcase 终态符合预期",
    "rubric_case_correctness": "每项评分标准和每个 testcase 判分正确",
    "testcase_contract_fairness": "Testcase 严格对应题面并检查功能而非固定写法",
    "hack_free": "模型没有联网取答案、搜索 Golden 或绕过评分",
    "windows_value": "题目具备真实 Windows 反事实价值",
    "scope_version_identity": "范围、版本、公式和全部执行资产身份已冻结",
    "wip94_complete": "WIP 94 项已逐项登记并提供证据或 N/A 依据",
    "dynamic_d01_d20_complete": "采购手册 D01-D20 已逐项完成动态审计",
    "independent_score_recompute": "已从 required testcase 和冻结公式独立复算正式分数",
    "evidence_retest_integrity": "原始证据、历史版本、整改和干净复验已闭环",
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_delivery_root(root: Path) -> Path:
    if (root / "task.toml").is_file():
        return root
    candidates = sorted({p.parent for p in root.rglob("task.toml") if "jobs" not in p.parts})
    if len(candidates) != 1:
        raise ValueError(f"cannot identify one direct Harbor Task root; found {len(candidates)} candidates")
    return candidates[0]


def quality_review_template() -> dict[str, Any]:
    return {
        key: {
            "status": "BLOCKED",
            "evidence": [],
            "notes": label,
        }
        for key, label in QUALITY_GATES.items()
    }


def load_quality_review(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "conclusion": "BLOCKED",
            "provided": False,
            "errors": ["未提供十项人工质量复核；自动检查通过也不能签发最终 PASS"],
            "items": quality_review_template(),
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "conclusion": "BLOCKED", "provided": True,
            "errors": [f"quality-review.json 无法读取：{type(exc).__name__}: {exc}"],
            "items": {},
        }
    if not isinstance(raw, dict):
        return {
            "conclusion": "BLOCKED", "provided": True,
            "errors": ["quality-review.json 顶层必须是对象"], "items": {},
        }
    errors: list[str] = []
    statuses: list[str] = []
    items: dict[str, Any] = {}
    for key, label in QUALITY_GATES.items():
        item = raw.get(key)
        if not isinstance(item, dict):
            errors.append(f"缺少质量复核项：{key}（{label}）")
            continue
        status = str(item.get("status") or "").strip().upper()
        evidence = item.get("evidence")
        notes = str(item.get("notes") or "").strip()
        if status not in {"PASS", "FAIL", "BLOCKED"}:
            errors.append(f"{key}.status 必须是 PASS/FAIL/BLOCKED")
        else:
            statuses.append(status)
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(value, str) and value.strip() for value in evidence
        ):
            errors.append(f"{key}.evidence 必须列出至少一项可定位证据")
        items[key] = {
            "label": label, "status": status or "BLOCKED",
            "evidence": evidence if isinstance(evidence, list) else [],
            "notes": notes,
        }
    if errors:
        conclusion = "BLOCKED"
    elif "FAIL" in statuses:
        conclusion = "FAIL"
    elif "BLOCKED" in statuses:
        conclusion = "BLOCKED"
    else:
        conclusion = "PASS"
    return {"conclusion": conclusion, "provided": True, "errors": errors, "items": items}


def markdown(payload: dict[str, Any]) -> str:
    lines = ["# Windows Harbor 完整质检报告", "", f"结论：**{payload['conclusion']}**", ""]
    lines += [f"- 交付目录：`{'PASS' if payload['delivery_layout']['pass'] else 'FAIL'}`",
              f"- 四模型门禁：`{'PASS' if payload['model_gate']['pass'] else 'FAIL'}`",
              f"- 四模型原始 jobs：`{'PASS' if payload['model_jobs']['pass'] else 'FAIL'}`",
              f"- Oracle/NOP：`{payload['harbor']['conclusion']}`",
              f"- 十项人工质量复核：`{payload['quality_review']['conclusion']}`", ""]
    sections = (("交付目录", payload["delivery_layout"]),
                ("模型门禁", payload["model_gate"]),
                ("模型 jobs", payload["model_jobs"]))
    for title, section in sections:
        lines += [f"## {title}", ""]
        for error in section.get("errors", []):
            lines.append(f"- 错误：{error}")
        for warning in section.get("warnings", []):
            lines.append(f"- 警告：{warning}")
        if not section.get("errors") and not section.get("warnings"):
            lines.append("- 通过")
        lines.append("")
    lines += ["## 十项人工质量硬门禁", ""]
    for key, label in QUALITY_GATES.items():
        item = payload["quality_review"].get("items", {}).get(key, {})
        lines.append(f"- **{label}**：`{item.get('status', 'BLOCKED')}`")
        for evidence in item.get("evidence") or []:
            lines.append(f"  - 证据：{evidence}")
        if item.get("notes"):
            lines.append(f"  - 说明：{item['notes']}")
    for error in payload["quality_review"].get("errors") or []:
        lines.append(f"- 错误：{error}")
    lines.append("")
    lines += ["## 原始证据", "",
              "- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志",
              "- `delivery-layout.json`：目录与 task_id/version/hash 绑定",
              "- `model-gate.json`：四模型次数、分数和区分度",
              "- `model-jobs.json`：14 个 Harbor jobs（8 个模型、3 个 Oracle、3 个 NOP）交叉校验",
              "- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件", ""]
    return "\n".join(lines)


def execute(args: argparse.Namespace) -> int:
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "quality-review-template.json", quality_review_template())
    source = args.input.resolve()
    if source.is_file() and source.suffix.casefold() == ".zip":
        unpacked = out / "input"
        safe_extract(source, unpacked)
        package_name_check = check_archive_root_name(source, unpacked)
        delivery = find_delivery_root(unpacked)
    elif source.is_dir():
        package_name_check = {"applicable": False, "pass": True, "errors": []}
        delivery = find_delivery_root(source)
    else:
        raise ValueError("--input must be a delivery directory or ZIP")

    layout = inspect_delivery(delivery)
    layout["package_name_check"] = package_name_check
    if not package_name_check["pass"]:
        layout["errors"].extend(package_name_check["errors"])
        layout["pass"] = False
    write_json(out / "delivery-layout.json", layout)
    try:
        jobs = validate_jobs(delivery / "jobs", delivery, layout.get("task") or {})
        gate = evaluate(jobs.get("evidence") or {}, layout.get("task") or None)
    except Exception as exc:
        gate = {"pass": False, "errors": [f"direct model jobs cannot be evaluated: {exc}"], "stats": {}}
        jobs = {"pass": False, "errors": [f"direct Harbor jobs cannot be evaluated: {exc}"],
                "warnings": [], "jobs": []}
    write_json(out / "model-gate.json", gate)
    write_json(out / "model-jobs.json", jobs)

    harbor_out = out / "harbor"
    if layout.get("task_root"):
        harbor_code = run_harbor_qc(SimpleNamespace(
            input=Path(layout["task_root"]), out=harbor_out,
            attempts=args.attempts, environment=args.environment,
            force_build=args.force_build,
        ))
        harbor_report_path = harbor_out / "report.json"
        harbor = json.loads(harbor_report_path.read_text(encoding="utf-8-sig")) if harbor_report_path.is_file() else {
            "conclusion": "BLOCKED", "reason": "Harbor QC did not create report.json"}
    else:
        harbor_code = 1
        harbor = {"conclusion": "FAIL", "reason": "no valid Task root was available"}

    quality_review = load_quality_review(getattr(args, "quality_review", None))
    write_json(out / "quality-review.json", quality_review)
    if harbor_code == 2 or harbor.get("conclusion") == "BLOCKED":
        automated_conclusion = "BLOCKED"
    elif layout["pass"] and gate["pass"] and jobs["pass"] and harbor.get("conclusion") == "PASS":
        automated_conclusion = "PASS"
    else:
        automated_conclusion = "FAIL"
    if automated_conclusion == "FAIL" or quality_review["conclusion"] == "FAIL":
        conclusion, exit_code = "FAIL", 1
    elif automated_conclusion == "BLOCKED" or quality_review["conclusion"] == "BLOCKED":
        conclusion, exit_code = "BLOCKED", 2
    else:
        conclusion, exit_code = "PASS", 0
    payload = {"conclusion": conclusion, "delivery_layout": layout,
               "model_gate": gate, "model_jobs": jobs, "harbor": harbor,
               "quality_review": quality_review,
               "automated_conclusion": automated_conclusion,
               "configuration": {"attempts": args.attempts, "job_format": "direct-harbor-jobs-v1"}}
    write_json(out / "report.json", payload)
    (out / "report.md").write_text(markdown(payload), encoding="utf-8")
    print(f"QC conclusion: {conclusion}")
    print(f"Report: {out / 'report.md'}")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="formal delivery directory or ZIP")
    parser.add_argument("--out", type=Path, required=True, help="new or empty result directory")
    parser.add_argument("--attempts", type=int, default=3, help="Oracle and NOP runs; minimum 3")
    parser.add_argument("--environment", help="Harbor environment import override")
    parser.add_argument("--force-build", action="store_true")
    parser.add_argument("--quality-review", type=Path,
                        help="十项人工质量复核 JSON；缺失时最终结论最多为 BLOCKED")
    args = parser.parse_args()
    if args.attempts < 3:
        parser.error("--attempts must be at least 3")
    try:
        return execute(args)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
