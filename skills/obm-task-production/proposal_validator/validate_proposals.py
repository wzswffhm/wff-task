#!/usr/bin/env python3
"""Validate proposal packages without network access or third-party packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MAPPING = SCRIPT_DIR / "benchmark_tasks.json"

BENCHMARKS = (
    "terminal_bench3",
    "terminal_bench4",
    "programbench",
    "swe_marathon",
    "deepSWE",
    "froniterSWE",
)
TOP_LEVEL_FIELDS = (
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
)
PROPOSAL_FIELDS = (
    "A_modification_idea",
    "B_modification_details",
    "C_agent_task",
    "D_task_difficulties",
)
IGNORED_SCAN_ENTRIES = {".DS_Store"}
WEB_URL_RE = re.compile(r"(?:https?|git|ssh)://[^\s<>\"']+", re.IGNORECASE)
SCP_GIT_URL_RE = re.compile(
    r"(?<![\w.-])git@[A-Za-z0-9.-]+:[A-Za-z0-9._~/-]+(?:\.git)?"
)
GIT_HOST_MARKERS = {
    "git",
    "gitea",
    "gitee",
    "github",
    "gitlab",
    "bitbucket",
    "codeberg",
    "sr",
}
DOMAIN_SEGMENT_RE = re.compile(r"^[^/\s](?:[^/\r\n\t]*[^/\s])?$")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}，。；：！？）】》"


class MappingError(Exception):
    """Raised when the bundled offline mapping is malformed."""


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains a duplicate key."""


@dataclass(frozen=True)
class Issue:
    code: str
    location: str
    message: str


@dataclass
class ValidationResult:
    package: str
    issues: list[Issue]

    @property
    def valid(self) -> bool:
        return not self.issues

    def as_json(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "valid": self.valid,
            "issues": [asdict(issue) for issue in self.issues],
        }


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"file is not valid UTF-8 (byte {exc.start}): {exc.reason}"
        ) from exc
    return json.loads(text, object_pairs_hook=_reject_duplicate_keys)


def load_mapping(path: Path) -> dict[str, Any]:
    try:
        data = load_json_file(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MappingError(f"cannot read mapping {path}: {exc}") from exc

    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise MappingError(f"{path} has an unsupported mapping schema")
    benchmarks = data.get("benchmarks")
    if not isinstance(benchmarks, dict):
        raise MappingError(f"{path} is missing the benchmarks object")

    for benchmark in BENCHMARKS:
        entry = benchmarks.get(benchmark)
        if not isinstance(entry, dict):
            raise MappingError(f"mapping is missing benchmark {benchmark!r}")
        tasks = entry.get("tasks")
        if not isinstance(tasks, dict) or not tasks:
            raise MappingError(f"mapping for {benchmark!r} has no task entries")
        if entry.get("task_count") != len(tasks):
            raise MappingError(
                f"mapping task_count for {benchmark!r} does not match its task entries"
            )
        policy = entry.get("domain_policy")
        if policy not in ("official_prefix", "freeform"):
            raise MappingError(f"mapping for {benchmark!r} has invalid domain_policy")
        for task_name, domain_prefix in tasks.items():
            if not isinstance(task_name, str) or not task_name:
                raise MappingError(
                    f"mapping for {benchmark!r} contains an invalid task name"
                )
            if policy == "official_prefix":
                if not isinstance(domain_prefix, str) or not domain_prefix:
                    raise MappingError(f"task {task_name!r} has no domain prefix")
            elif domain_prefix is not None:
                raise MappingError(
                    f"freeform task {task_name!r} must use a null domain prefix"
                )
    return data


def _add_type_issue(
    issues: list[Issue], location: str, expected: str, value: Any
) -> None:
    issues.append(
        Issue(
            "invalid_type",
            location,
            f"expected {expected}, got {type(value).__name__}",
        )
    )


def _validate_exact_fields(
    value: dict[str, Any],
    required_fields: Iterable[str],
    location: str,
    issues: list[Issue],
) -> None:
    required = set(required_fields)
    actual = set(value)
    for field in sorted(required - actual):
        issues.append(
            Issue(
                "missing_field",
                f"{location}.{field}",
                "required field is missing",
            )
        )
    for field in sorted(actual - required):
        issues.append(
            Issue(
                "unexpected_field",
                f"{location}.{field}",
                "field is not present in the proposal template",
            )
        )


def _validate_nonempty_string(value: Any, location: str, issues: list[Issue]) -> bool:
    if type(value) is not str:
        _add_type_issue(issues, location, "string", value)
        return False
    if not value.strip():
        issues.append(Issue("empty_string", location, "value must not be empty"))
        return False
    return True


def _domain_segments(value: Any, issues: list[Issue]) -> list[str] | None:
    if not _validate_nonempty_string(value, "$.domain", issues):
        return None

    segments = value.split("/")
    if not 2 <= len(segments) <= 3:
        issues.append(
            Issue(
                "invalid_domain_depth",
                "$.domain",
                "domain must contain 2 or 3 slash-separated levels",
            )
        )
        return None

    valid = True
    for index, segment in enumerate(segments):
        if not DOMAIN_SEGMENT_RE.fullmatch(segment):
            issues.append(
                Issue(
                    "invalid_domain_segment",
                    f"$.domain[{index}]",
                    "domain levels must be non-empty and have no surrounding whitespace",
                )
            )
            valid = False
    return segments if valid else None


def _contains_git_repository_url(value: str) -> bool:
    if SCP_GIT_URL_RE.search(value):
        return True

    for raw_url in WEB_URL_RE.findall(value):
        url = raw_url.rstrip(TRAILING_URL_PUNCTUATION)
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https", "git", "ssh") or not parsed.hostname:
            continue
        path_parts = [
            part
            for part in parsed.path.removesuffix(".git").split("/")
            if part and part not in (".", "..")
        ]
        host_markers = set(parsed.hostname.lower().split("."))
        is_git_host = bool(host_markers & GIT_HOST_MARKERS)
        is_explicit_git_url = (
            parsed.scheme in ("git", "ssh")
            or parsed.path.lower().endswith(".git")
            or parsed.username == "git"
        )
        # Hosting URLs need an owner/group and repository. Explicit Git
        # transport URLs may use a single repository path component.
        if (is_git_host and len(path_parts) >= 2) or (
            is_explicit_git_url and path_parts
        ):
            return True
    return False


def validate_document(
    document: Any,
    folder_name: str,
    mapping: dict[str, Any],
) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(document, dict):
        _add_type_issue(issues, "$", "object", document)
        return issues

    _validate_exact_fields(document, TOP_LEVEL_FIELDS, "$", issues)

    benchmark = document.get("benchmark")
    benchmark_valid = _validate_nonempty_string(benchmark, "$.benchmark", issues)
    if benchmark_valid and benchmark not in BENCHMARKS:
        issues.append(
            Issue(
                "invalid_benchmark",
                "$.benchmark",
                "must be one of: {}".format(", ".join(BENCHMARKS)),
            )
        )
        benchmark_valid = False

    if benchmark_valid:
        required_prefix = benchmark + "_"
        proposal_name = (
            folder_name[len(required_prefix) :]
            if folder_name.startswith(required_prefix)
            else ""
        )
        if not proposal_name.strip():
            issues.append(
                Issue(
                    "folder_name_mismatch",
                    ".",
                    f"folder name must be '{required_prefix}<proposal_name>'",
                )
            )

    domain_parts = _domain_segments(document.get("domain"), issues)

    related_question = document.get("related_question")
    related_valid = _validate_nonempty_string(
        related_question, "$.related_question", issues
    )

    proposal_type = document.get("proposal_type")
    proposal_type_valid = _validate_nonempty_string(
        proposal_type, "$.proposal_type", issues
    )
    if proposal_type_valid and proposal_type not in ("A", "B", "C"):
        issues.append(
            Issue(
                "invalid_proposal_type",
                "$.proposal_type",
                "must be exactly A, B, or C",
            )
        )
        proposal_type_valid = False

    allow_network = document.get("allow_network")
    if type(allow_network) is not bool:
        _add_type_issue(issues, "$.allow_network", "boolean", allow_network)

    proposal = document.get("proposal")
    if not isinstance(proposal, dict):
        _add_type_issue(issues, "$.proposal", "object", proposal)
    else:
        _validate_exact_fields(proposal, PROPOSAL_FIELDS, "$.proposal", issues)
        for field in PROPOSAL_FIELDS[:3]:
            _validate_nonempty_string(
                proposal.get(field), "$.proposal." + field, issues
            )
        difficulties = proposal.get("D_task_difficulties")
        if not isinstance(difficulties, list):
            _add_type_issue(
                issues,
                "$.proposal.D_task_difficulties",
                "array of strings",
                difficulties,
            )
        elif not difficulties:
            issues.append(
                Issue(
                    "empty_array",
                    "$.proposal.D_task_difficulties",
                    "at least one difficulty is required",
                )
            )
        else:
            for index, difficulty in enumerate(difficulties):
                _validate_nonempty_string(
                    difficulty,
                    f"$.proposal.D_task_difficulties[{index}]",
                    issues,
                )

    for field in (
        "proposal_sources",
        "proposal_scene",
        "proposal_verify",
        "expert_experience_skill",
    ):
        _validate_nonempty_string(document.get(field), "$." + field, issues)

    proposal_sources = document.get("proposal_sources")
    if (
        proposal_type in ("A", "B")
        and isinstance(proposal_sources, str)
        and proposal_sources.strip()
        and not _contains_git_repository_url(proposal_sources)
    ):
        issues.append(
            Issue(
                "missing_git_repository_url",
                "$.proposal_sources",
                "proposal types A and B must contain a plausible Git repository URL",
            )
        )

    if benchmark_valid and related_valid:
        benchmark_entry = mapping["benchmarks"][benchmark]
        tasks = benchmark_entry["tasks"]
        if related_question not in tasks:
            issues.append(
                Issue(
                    "unknown_related_question",
                    "$.related_question",
                    f"{related_question!r} is not a task folder in benchmark {benchmark!r}",
                )
            )
        elif (
            domain_parts is not None
            and benchmark_entry["domain_policy"] == "official_prefix"
        ):
            expected_prefix = tasks[related_question].split("/")
            actual_prefix = domain_parts[: len(expected_prefix)]
            if actual_prefix != expected_prefix:
                issues.append(
                    Issue(
                        "domain_mismatch",
                        "$.domain",
                        "expected official prefix {!r} for task {!r}".format(
                            "/".join(expected_prefix), related_question
                        ),
                    )
                )

    return issues


def validate_package(package: Path, mapping: dict[str, Any]) -> ValidationResult:
    issues: list[Issue] = []
    package = package.resolve()

    if not package.exists():
        return ValidationResult(
            str(package),
            [Issue("path_not_found", ".", "package path does not exist")],
        )
    if not package.is_dir():
        return ValidationResult(
            str(package),
            [Issue("not_a_directory", ".", "package path must be a directory")],
        )

    expected_entries = {"proposal.json", "sources"}
    try:
        actual_entries = {entry.name for entry in package.iterdir()}
    except OSError as exc:
        return ValidationResult(
            str(package),
            [Issue("directory_read_error", ".", str(exc))],
        )

    for name in sorted(expected_entries - actual_entries):
        issues.append(Issue("missing_entry", name, "required package entry is missing"))
    for name in sorted(actual_entries - expected_entries):
        issues.append(
            Issue(
                "unexpected_entry",
                name,
                "package root may contain only proposal.json and sources",
            )
        )

    proposal_path = package / "proposal.json"
    sources_path = package / "sources"
    if proposal_path.exists() and not proposal_path.is_file():
        issues.append(
            Issue("wrong_entry_type", "proposal.json", "must be a regular file")
        )
    if sources_path.exists() and not sources_path.is_dir():
        issues.append(Issue("wrong_entry_type", "sources", "must be a directory"))

    if proposal_path.is_file():
        try:
            document = load_json_file(proposal_path)
        except OSError as exc:
            issues.append(Issue("json_read_error", "proposal.json", str(exc)))
        except DuplicateKeyError as exc:
            issues.append(Issue("duplicate_json_key", "proposal.json", str(exc)))
        except json.JSONDecodeError as exc:
            issues.append(
                Issue(
                    "invalid_json",
                    f"proposal.json:{exc.lineno}:{exc.colno}",
                    exc.msg,
                )
            )
        except ValueError as exc:
            issues.append(Issue("invalid_json_encoding", "proposal.json", str(exc)))
        else:
            issues.extend(validate_document(document, package.name, mapping))

    return ValidationResult(str(package), issues)


def discover_packages(target: Path) -> tuple[list[Path], list[Issue]]:
    target = target.resolve()
    if not target.exists():
        return [], [Issue("path_not_found", str(target), "target does not exist")]
    if not target.is_dir():
        return [], [Issue("not_a_directory", str(target), "target must be a directory")]

    looks_like_package = any(
        target.name.startswith(benchmark + "_") for benchmark in BENCHMARKS
    )
    if (
        looks_like_package
        or (target / "proposal.json").exists()
        or (target / "sources").exists()
    ):
        return [target], []

    packages: list[Path] = []
    issues: list[Issue] = []
    for entry in sorted(target.iterdir(), key=lambda item: item.name):
        if entry.name in IGNORED_SCAN_ENTRIES:
            continue
        if entry.is_dir():
            packages.append(entry)
        else:
            issues.append(
                Issue(
                    "unexpected_scan_entry",
                    str(entry),
                    "a collection directory may contain only proposal package directories",
                )
            )
    if not packages:
        issues.append(
            Issue(
                "no_packages",
                str(target),
                "no proposal package directories were found",
            )
        )
    return packages, issues


def _print_text(results: list[ValidationResult], scan_issues: list[Issue]) -> None:
    for issue in scan_issues:
        print(f"[FAIL] {issue.location}: {issue.message} ({issue.code})")
    for result in results:
        print("[{}] {}".format("OK" if result.valid else "FAIL", result.package))
        for issue in result.issues:
            print(f"  - {issue.location}: {issue.message} ({issue.code})")
    failed = sum(not result.valid for result in results)
    print(
        f"\nValidated {len(results)} package(s): {len(results) - sum(not r.valid for r in results)} passed, {failed} failed."
    )
    if scan_issues:
        print(f"Collection-level errors: {len(scan_issues)}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one proposal package or each immediate package directory "
            "inside a collection directory."
        )
    )
    parser.add_argument("paths", nargs="+", type=Path, help="package or collection")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
        help="offline benchmark mapping (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="emit a machine-readable JSON report",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        mapping = load_mapping(args.mapping)
    except MappingError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    packages: list[Path] = []
    scan_issues: list[Issue] = []
    for target in args.paths:
        discovered, discovery_issues = discover_packages(target)
        packages.extend(discovered)
        scan_issues.extend(discovery_issues)

    results = [validate_package(package, mapping) for package in packages]
    if args.json_output:
        print(
            json.dumps(
                {
                    "valid": not scan_issues
                    and all(result.valid for result in results),
                    "scan_issues": [asdict(issue) for issue in scan_issues],
                    "results": [result.as_json() for result in results],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _print_text(results, scan_issues)

    return 0 if not scan_issues and all(result.valid for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
