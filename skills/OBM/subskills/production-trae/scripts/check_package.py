#!/usr/bin/env python3
"""Run static preflight checks on an OBM Source package."""

from __future__ import annotations

import argparse
import json
import re
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from check_skill_language import analyze_skill_language


FORBIDDEN_PARTS = {
    ".git",
    ".DS_Store",
    "__MACOSX",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}
ANSWER_NAMES = {"solution", "reference_solution", "answer", "oracle_patch"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def ok(self, message: str) -> None:
        self.passes.append(message)


def safe_extract(archive: Path, destination: Path, report: Report) -> Path | None:
    try:
        with zipfile.ZipFile(archive) as zf:
            infos = zf.infolist()
            if not infos:
                report.error("ZIP is empty")
                return None
            for info in infos:
                name = PurePosixPath(info.filename)
                if name.is_absolute() or ".." in name.parts:
                    report.error(f"unsafe ZIP member: {info.filename}")
                    return None
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    report.error(f"ZIP contains symlink: {info.filename}")
                    return None
            zf.extractall(destination)
            # zipfile.extractall does not restore Unix executable bits.
            # Reapply the stored mode so verifier entrypoints are checked
            # against the archive as submitted instead of the temp defaults.
            for info in infos:
                mode = (info.external_attr >> 16) & 0o7777
                if not mode or info.is_dir():
                    continue
                extracted = destination / PurePosixPath(info.filename)
                if extracted.is_file():
                    extracted.chmod(mode)
    except (OSError, zipfile.BadZipFile) as exc:
        report.error(f"cannot read ZIP: {exc}")
        return None

    roots = [p for p in destination.iterdir() if p.name not in FORBIDDEN_PARTS]
    if len(roots) != 1 or not roots[0].is_dir():
        report.error("ZIP must contain exactly one task root directory")
        return None
    report.ok("ZIP is readable and has one task root")
    return roots[0]


def find_root(path: Path, temp: Path, report: Report) -> Path | None:
    if path.is_dir():
        return path
    if path.is_file() and path.suffix.lower() == ".zip":
        return safe_extract(path, temp, report)
    report.error("input must be a task directory or ZIP")
    return None


def read_text(path: Path, report: Report) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.error(f"cannot read {path}: {exc}")
        return ""


def require(root: Path, rel: str, report: Report, executable: bool = False) -> Path:
    path = root / rel
    if not path.is_file():
        report.error(f"missing required file: {rel}")
        return path
    if executable and not (path.stat().st_mode & 0o111):
        report.error(f"file is not executable: {rel}")
    else:
        report.ok(f"found {rel}")
    return path


def check_common(root: Path, report: Report) -> dict:
    proposal_path = require(root, "proposal.json", report)
    if not proposal_path.is_file():
        return {}
    try:
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.error(f"invalid proposal.json: {exc}")
        return {}

    required_top = {
        "benchmark",
        "domain",
        "related_question",
        "proposal_type",
        "allow_network",
        "proposal",
        "proposal_sources",
        "proposal_scene",
        "proposal_verify",
        "expert_experience_skill",
    }
    missing = sorted(required_top - proposal.keys())
    if missing:
        report.error("proposal.json missing fields: " + ", ".join(missing))

    body = proposal.get("proposal")
    if not isinstance(body, dict):
        report.error("proposal must be an object")
        body = {}
    required_body = {
        "A_modification_idea",
        "B_modification_details",
        "C_agent_task",
        "D_task_difficulties",
    }
    missing_body = sorted(required_body - body.keys())
    if missing_body:
        report.error("proposal object missing fields: " + ", ".join(missing_body))

    domain = proposal.get("domain")
    if not isinstance(domain, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_ &+.-]*(/[A-Za-z][A-Za-z0-9_ &+.-]*)+", domain
    ):
        report.error("domain must be an English hierarchy using half-width '/'")

    difficulties = body.get("D_task_difficulties")
    if not isinstance(difficulties, list) or not difficulties or not all(
        isinstance(item, str) and item.strip() for item in difficulties
    ):
        report.error("D_task_difficulties must be a non-empty string array")

    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(part in FORBIDDEN_PARTS for part in rel_parts):
            report.error(f"forbidden generated or hidden path: {path.relative_to(root)}")
        lowered = {part.lower() for part in rel_parts}
        if lowered & ANSWER_NAMES:
            report.error(f"possible answer material in formal package: {path.relative_to(root)}")
        if path.is_file() and path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
            report.error(f"possible credential file: {path.relative_to(root)}")

    return proposal


def check_deepswe(root: Path, proposal: dict, report: Report) -> None:
    if proposal.get("benchmark") != "deepSWE":
        report.error("deepSWE benchmark enum must be exactly 'deepSWE'")
    else:
        report.ok("benchmark enum is deepSWE")

    required = [
        ("sources/app/Dockerfile", False),
        ("sources/README.md", False),
        ("sources/app/upstream.tar.gz", False),
        ("sources/skill/SKILL.md", False),
        ("sources/verifier/Dockerfile", False),
        ("sources/verifier/test.sh", True),
        ("sources/verifier/grader.py", True),
        ("sources/verifier/config.json", False),
        ("sources/verifier/test.patch", False),
    ]
    paths = {rel: require(root, rel, report, exe) for rel, exe in required}

    instruction_path = root / "sources/app/instruction.md"
    if instruction_path.exists():
        report.error("formal deepSWE package must not include sources/app/instruction.md")

    docker = read_text(paths["sources/app/Dockerfile"], report)
    commands = {
        "apt-get": r"\bapt-get\b",
        "git clone": r"\bgit\s+clone\b",
        "curl": r"\bcurl\b",
        "wget": r"\bwget\b",
    }
    for label, pattern in commands.items():
        if re.search(pattern, docker, re.IGNORECASE):
            report.error(f"Agent Dockerfile contains network-dependent command: {label}")
    if re.search(r"\b(?:pip|python\s+-m\s+pip)\s+install\b", docker):
        if "--no-index" not in docker:
            report.error("pip install must use an offline source such as --no-index")
    if "@sha256:" not in docker:
        report.warn("base image is not pinned by digest")

    skill = read_text(paths["sources/skill/SKILL.md"], report)
    if "AGENT_TASK.md" in skill:
        report.error("task skill references legacy AGENT_TASK.md")
    if "instruction.md" in skill:
        report.error("task skill must not depend on sources/app/instruction.md")

    language = analyze_skill_language(skill)
    if language["issues"]:
        for issue in language["issues"]:
            report.error(f"task skill must be written in Chinese: {issue}")
    else:
        report.ok(
            "task skill is Chinese-language prose "
            f"(CJK={language['cjk_chars']}, Latin={language['latin_chars']})"
        )

    difficulties = proposal.get("proposal", {}).get("D_task_difficulties", [])
    heading_count = len(re.findall(r"^#{2,4}\s+", skill, re.MULTILINE))
    if isinstance(difficulties, list) and heading_count < len(difficulties):
        report.warn(
            "task skill has fewer headings than task difficulties; manually verify one-to-one coverage"
        )
    report.warn(
        "manual gate: map every D_task_difficulties item to a task-specific skill section "
        "and verifier behavior; generic invariant advice is insufficient"
    )

    config_path = paths["sources/verifier/config.json"]
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(config.get("f2p_node_ids"), list) or not config["f2p_node_ids"]:
                report.error("verifier config needs a non-empty f2p_node_ids list")
            if not isinstance(config.get("p2p_node_ids"), list) or not config["p2p_node_ids"]:
                report.error("verifier config needs a non-empty p2p_node_ids list")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            report.error(f"invalid verifier config.json: {exc}")

    if proposal.get("allow_network") is not False:
        report.warn("deepSWE OBM tasks normally use allow_network=false; verify current rules")


def print_report(report: Report, as_json: bool) -> None:
    payload = {
        "ok": not report.errors,
        "errors": report.errors,
        "warnings": report.warnings,
        "passes": report.passes,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for label, rows in (
        ("PASS", report.passes),
        ("WARN", report.warnings),
        ("FAIL", report.errors),
    ):
        for row in rows:
            print(f"[{label}] {row}")
    print(
        f"Result: {'PASS' if not report.errors else 'FAIL'} "
        f"({len(report.errors)} errors, {len(report.warnings)} warnings)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="task directory or ZIP")
    parser.add_argument("--benchmark", default="deepSWE")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    report = Report()
    with tempfile.TemporaryDirectory(prefix="obm-check-") as tmp:
        root = find_root(args.package.expanduser().resolve(), Path(tmp), report)
        if root is not None:
            proposal = check_common(root, report)
            if args.benchmark == "deepSWE":
                check_deepswe(root, proposal, report)
            else:
                report.warn(
                    f"no benchmark-specific checker for {args.benchmark}; only common checks ran"
                )
    print_report(report, args.as_json)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
