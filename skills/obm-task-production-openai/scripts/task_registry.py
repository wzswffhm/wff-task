#!/usr/bin/env python3
"""Maintain the shared OBM task registry and reserve task IDs atomically."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


SCHEMA_VERSION = 1
ACTIVE_STATUSES = {"reserved", "candidate", "packaged"}
VALID_STATUSES = ACTIVE_STATUSES | {"rejected", "abandoned"}
TASK_ID_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2}-\d+)(?!\d)")
GITHUB_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?=[^A-Za-z0-9_.-]|$)"
)
COMMIT_RE = re.compile(r"(?<![0-9a-f])([0-9a-f]{40})(?![0-9a-f])", re.IGNORECASE)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def registry_paths(root: Path) -> tuple[Path, Path]:
    work = root / "work"
    return work / "task-registry.json", work / "task-registry.lock"


def empty_registry() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "updated_at": utc_now(), "entries": []}


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_registry()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION or not isinstance(data.get("entries"), list):
        raise ValueError(f"unsupported or invalid registry: {path}")
    return data


def write_registry(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = utc_now()
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def locked_registry(root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    registry_path, lock_path = registry_paths(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        data = load_registry(registry_path)
        yield registry_path, data
        write_registry(registry_path, data)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def project_relative(path: Path, root: Path) -> str:
    root = root.resolve()
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError as exc:
        raise ValueError(f"path must stay inside the project root: {path}") from exc


def proposal_files(root: Path) -> list[Path]:
    ignored = {".git", ".codex", "Benchmark", "node_modules", ".venv", "venv"}
    found: list[Path] = []
    for path in root.rglob("proposal.json"):
        rel = path.relative_to(root)
        if any(part in ignored for part in rel.parts):
            continue
        found.append(path)
    return sorted(found)


def proposal_task_id(package_name: str, proposal: dict[str, Any]) -> Optional[str]:
    candidates = [package_name]
    inner = proposal.get("proposal")
    if isinstance(inner, dict):
        candidates.extend(str(value) for value in inner.values() if isinstance(value, str))
    for value in candidates:
        match = TASK_ID_RE.search(value)
        if match:
            return match.group(1)
    return None


def strip_package_prefix(package_name: str, benchmark: str) -> str:
    prefix = f"{benchmark}_"
    if package_name.casefold().startswith(prefix.casefold()):
        return package_name[len(prefix) :]
    return package_name


def slug_from_name(proposal_name: str, task_id: Optional[str]) -> str:
    if task_id and proposal_name.startswith(f"{task_id}-"):
        return proposal_name[len(task_id) + 1 :]
    return proposal_name


def extract_source(proposal: dict[str, Any]) -> tuple[str, str]:
    source = str(proposal.get("proposal_sources", ""))
    repo_match = GITHUB_RE.search(source)
    commit_match = COMMIT_RE.search(source)
    repository = repo_match.group(1) if repo_match else "unknown"
    commit = commit_match.group(1).lower() if commit_match else "unknown"
    return repository, commit


def proposal_fingerprint(proposal: dict[str, Any]) -> str:
    contract = proposal.get("proposal", {})
    return sha256_json(
        {
            "benchmark": proposal.get("benchmark"),
            "scene": proposal.get("proposal_scene"),
            "contract": contract,
            "verify": proposal.get("proposal_verify"),
        }
    )


def imported_entry(path: Path, root: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    package_name = path.parent.name
    benchmark = str(proposal.get("benchmark", "unknown"))
    proposal_name = strip_package_prefix(package_name, benchmark)
    task_id = proposal_task_id(package_name, proposal)
    repository, base_commit = extract_source(proposal)
    stamp = utc_now()
    package_path = project_relative(path.parent, root)
    return {
        "reservation_id": f"imported-{hashlib.sha256(package_path.encode()).hexdigest()[:16]}",
        "benchmark": benchmark,
        "task_id": task_id,
        "proposal_name": proposal_name,
        "slug": slug_from_name(proposal_name, task_id),
        "status": "packaged",
        "repository": repository,
        "base_commit": base_commit,
        "capability_type": str(proposal.get("domain", "unclassified")),
        "scene_summary": str(proposal.get("proposal_scene", "")),
        "scene_fingerprint": proposal_fingerprint(proposal),
        "reference_tasks": [str(proposal.get("related_question"))] if proposal.get("related_question") else [],
        "paths": {"package": package_path},
        "created_at": stamp,
        "updated_at": stamp,
        "source": "filesystem-import",
    }


def collapse_import_duplicates(entries: list[dict[str, Any]]) -> int:
    """Fold filesystem imports back into their unique reservation record.

    A packaged reservation may point at the final ZIP while proposal discovery
    sees the unpacked package directory.  Those are two paths for the same
    proposal, not two registry entries.
    """
    removed = 0
    for imported in list(entries):
        if imported.get("source") != "filesystem-import":
            continue
        matches = [
            entry
            for entry in entries
            if entry is not imported
            and entry.get("source") == "reservation"
            and entry.get("benchmark") == imported.get("benchmark")
            and entry.get("proposal_name") == imported.get("proposal_name")
            and entry.get("scene_fingerprint") == imported.get("scene_fingerprint")
        ]
        if len(matches) != 1:
            continue
        reservation = matches[0]
        imported_path = imported.get("paths", {}).get("package")
        if imported_path:
            reservation.setdefault("paths", {})["package_dir"] = imported_path
        entries.remove(imported)
        removed += 1
    return removed


def merge_existing(data: dict[str, Any], root: Path) -> tuple[int, list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = data["entries"]
    collapse_import_duplicates(entries)
    imported = 0
    by_package = {
        entry.get("paths", {}).get("package"): entry
        for entry in entries
        if entry.get("paths", {}).get("package")
    }
    for proposal_path in proposal_files(root):
        try:
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        candidate = imported_entry(proposal_path, root, proposal)
        package_path = candidate["paths"]["package"]
        existing = by_package.get(package_path)
        if existing is None:
            matching = [
                entry
                for entry in entries
                if entry.get("proposal_name") == candidate["proposal_name"]
                and entry.get("benchmark") == candidate["benchmark"]
                and entry.get("status") in ACTIVE_STATUSES
            ]
            existing = matching[0] if len(matching) == 1 else None
        if existing is None:
            entries.append(candidate)
            by_package[package_path] = candidate
            imported += 1
        else:
            created_at = existing.get("created_at", candidate["created_at"])
            reservation_id = existing.get("reservation_id", candidate["reservation_id"])
            source = existing.get("source", candidate["source"])
            registered_package = existing.get("paths", {}).get("package")
            existing.update(candidate)
            if source == "reservation" and registered_package:
                existing["paths"] = {
                    "package": registered_package,
                    "package_dir": package_path,
                }
            existing["created_at"] = created_at
            existing["reservation_id"] = reservation_id
            existing["source"] = source
            existing["updated_at"] = utc_now()
    return imported, id_collisions(entries)


def id_collisions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for entry in entries:
        task_id = entry.get("task_id")
        if task_id:
            grouped.setdefault(task_id, []).append(str(entry.get("proposal_name")))
    return [
        {"task_id": task_id, "proposal_names": sorted(names)}
        for task_id, names in sorted(grouped.items())
        if len(names) > 1
    ]


def existing_numbers(root: Path, entries: list[dict[str, Any]], day: str) -> list[int]:
    numbers: set[int] = set()
    pattern = re.compile(rf"^{re.escape(day)}-(\d+)(?:$|[-_])")
    for entry in entries:
        task_id = str(entry.get("task_id") or "")
        match = pattern.match(task_id)
        if match:
            numbers.add(int(match.group(1)))
    for path in root.rglob("*"):
        match = pattern.match(path.name)
        if match:
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def scene_fingerprint(args: argparse.Namespace) -> str:
    if args.scene_profile:
        profile = json.loads(args.scene_profile.read_text(encoding="utf-8"))
        return sha256_json(profile)
    return sha256_json(
        {
            "benchmark": args.benchmark,
            "repository": args.repository,
            "capability_type": args.capability_type,
            "scene_summary": normalize_text(args.scene_summary),
        }
    )


def reserve(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise ValueError("date must use YYYY-MM-DD")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug):
        raise ValueError("slug must be lowercase kebab-case")
    with locked_registry(root) as (_, data):
        _, collisions = merge_existing(data, root)
        fingerprint = scene_fingerprint(args)
        slug_key = normalize_text(args.slug)
        blockers = []
        for entry in data["entries"]:
            if entry.get("status") not in ACTIVE_STATUSES:
                continue
            if normalize_text(str(entry.get("slug", ""))) == slug_key:
                blockers.append({"reason": "same slug", "entry": entry})
            elif entry.get("scene_fingerprint") == fingerprint:
                blockers.append({"reason": "same scene fingerprint", "entry": entry})
        if blockers:
            detail = "; ".join(
                f"{item['reason']}: {item['entry'].get('proposal_name')}"
                for item in blockers
            )
            raise ValueError(f"reservation rejected: {detail}")

        numbers = existing_numbers(root, data["entries"], args.date)
        number = max(numbers, default=0) + 1
        task_id = f"{args.date}-{number}"
        proposal_name = f"{task_id}-{args.slug}"
        stamp = utc_now()
        entry = {
            "reservation_id": str(uuid.uuid4()),
            "benchmark": args.benchmark,
            "task_id": task_id,
            "proposal_name": proposal_name,
            "slug": args.slug,
            "status": "reserved",
            "repository": args.repository,
            "base_commit": args.base_commit,
            "capability_type": args.capability_type,
            "scene_summary": args.scene_summary,
            "scene_fingerprint": fingerprint,
            "reference_tasks": args.reference_task,
            "paths": {
                "candidate": f"work/candidates/{args.slug}",
                "work": f"work/{proposal_name}",
                "package": f"output/{args.benchmark}_{proposal_name}",
            },
            "created_at": stamp,
            "updated_at": stamp,
            "source": "reservation",
        }
        data["entries"].append(entry)
        similar = [
            {
                "proposal_name": other.get("proposal_name"),
                "repository": other.get("repository"),
                "capability_type": other.get("capability_type"),
                "scene_summary": other.get("scene_summary"),
            }
            for other in data["entries"]
            if other is not entry
            and other.get("status") in ACTIVE_STATUSES
            and (
                normalize_text(str(other.get("repository", "")))
                == normalize_text(args.repository)
                or normalize_text(str(other.get("capability_type", "")))
                == normalize_text(args.capability_type)
            )
        ]
        return {"reserved": entry, "similar_entries_for_review": similar, "existing_id_collisions": collisions}


def update(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    with locked_registry(root) as (_, data):
        merge_existing(data, root)
        matches = [entry for entry in data["entries"] if entry.get("reservation_id") == args.reservation_id]
        if len(matches) != 1:
            raise ValueError("reservation_id not found or is ambiguous")
        entry = matches[0]
        if args.status == "candidate":
            dedup = entry.get("dedup")
            if not isinstance(dedup, dict) or dedup.get("conclusion") != "distinct":
                raise ValueError(
                    "candidate status requires a verified distinct result from register_scene_dedup.py"
                )
            required = {"local_record_path", "feishu_record_id", "annotator_open_id", "synced_at"}
            if any(not dedup.get(key) for key in required):
                raise ValueError(
                    "candidate status requires local and Feishu scene-dedup evidence"
                )
        entry["status"] = args.status
        if args.package_path:
            entry.setdefault("paths", {})["package"] = project_relative(args.package_path, root)
        if args.note:
            entry["note"] = args.note
        entry["updated_at"] = utc_now()
        return entry


def sync(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    with locked_registry(root) as (path, data):
        imported, collisions = merge_existing(data, root)
        return {
            "registry": str(path),
            "imported": imported,
            "entries": len(data["entries"]),
            "id_collisions": collisions,
        }


def list_entries(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    with locked_registry(root) as (path, data):
        merge_existing(data, root)
        entries = data["entries"]
        if args.status:
            entries = [entry for entry in entries if entry.get("status") == args.status]
        return {"registry": str(path), "entries": entries, "id_collisions": id_collisions(data["entries"])}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=Path.cwd())

    sync_parser = sub.add_parser("sync", parents=[common], help="import existing proposal packages")
    sync_parser.set_defaults(func=sync)

    list_parser = sub.add_parser("list", parents=[common], help="list registered tasks")
    list_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    list_parser.set_defaults(func=list_entries)

    reserve_parser = sub.add_parser("reserve", parents=[common], help="atomically reserve a new task")
    reserve_parser.add_argument("--date", default=dt.date.today().isoformat())
    reserve_parser.add_argument("--benchmark", required=True)
    reserve_parser.add_argument("--slug", required=True)
    reserve_parser.add_argument("--repository", required=True)
    reserve_parser.add_argument("--base-commit", default="unknown")
    reserve_parser.add_argument("--capability-type", required=True)
    reserve_parser.add_argument("--scene-summary", required=True)
    reserve_parser.add_argument("--scene-profile", type=Path)
    reserve_parser.add_argument("--reference-task", action="append", default=[])
    reserve_parser.set_defaults(func=reserve)

    update_parser = sub.add_parser("update", parents=[common], help="update one reservation")
    update_parser.add_argument("--reservation-id", required=True)
    update_parser.add_argument("--status", choices=sorted(VALID_STATUSES), required=True)
    update_parser.add_argument("--package-path", type=Path)
    update_parser.add_argument("--note")
    update_parser.set_defaults(func=update)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "scene_profile", None):
        args.scene_profile = args.scene_profile.expanduser().resolve()
    try:
        result = args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
