"""Inspect one direct Harbor Windows task delivery and its immutable identity."""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any


TASK_ROOT_ITEMS = ("task.toml", "instruction.md", "environment", "solution", "tests", "jobs")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_files(root: Path):
    """Yield delivered Task files, excluding the post-run jobs evidence tree."""
    return sorted(
        (path for path in root.rglob("*")
         if path.is_file() and path.relative_to(root).parts[0].casefold() != "jobs"),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def task_hash(root: Path) -> str:
    lines = [f"{path.relative_to(root).as_posix()}\t{sha256(path)}\n"
             for path in task_files(root)]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def harbor_dirhash(root: Path) -> str:
    """Reproduce Harbor dirhash for the Task while excluding delivered jobs/."""
    root = root.resolve()

    def visit(directory: Path) -> str | None:
        descriptors: list[str] = []
        for path in directory.iterdir():
            if directory == root and path.name.casefold() == "jobs":
                continue
            if path.is_symlink():
                raise ValueError(f"symbolic links are not allowed in a formal Task: {path}")
            if path.is_file():
                properties = sorted((f"data:{sha256(path)}", f"name:{path.name}"))
                descriptors.append("\0".join(properties))
            elif path.is_dir():
                child = visit(path)
                if child is not None:
                    properties = sorted((f"dirhash:{child}", f"name:{path.name}"))
                    descriptors.append("\0".join(properties))
        if not descriptors:
            return None
        return hashlib.sha256("\0\0".join(sorted(descriptors)).encode("utf-8")).hexdigest()

    value = visit(root)
    if value is None:
        raise ValueError(f"Task directory is empty: {root}")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError("TOML root is not an object")
    return value


def task_id_from_toml(path: Path) -> tuple[str | None, str | None, str | None, dict[str, Any]]:
    value = load_toml(path)
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
    task = value.get("task") if isinstance(value.get("task"), dict) else {}
    task_id = metadata.get("task_id") or task.get("id") or task.get("name") or value.get("task_id")
    version = task.get("version") or metadata.get("task_version") or value.get("task_version")
    image = value.get("docker_image") or ((value.get("environment") or {}).get("docker_image"))
    return task_id, version, image, value


def inspect_delivery(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for name in TASK_ROOT_ITEMS:
        if not (root / name).exists():
            errors.append(f"missing direct Harbor root item: {name}{'/' if '.' not in name else ''}")
    for legacy in ("outside_harbor", "outside_harbor-assets"):
        if (root / legacy).exists():
            errors.append(f"legacy Demo wrapper is not accepted: {legacy}/")

    identity: dict[str, Any] = {}
    config: dict[str, Any] = {}
    task_toml = root / "task.toml"
    if task_toml.is_file():
        try:
            task_id, task_version, image, config = task_id_from_toml(task_toml)
            identity = {
                "task_id": task_id,
                "task_version": task_version,
                "task_hash": task_hash(root),
                "harbor_task_checksum": harbor_dirhash(root),
            }
            for field in ("task_id", "task_version", "task_hash", "harbor_task_checksum"):
                if not identity.get(field):
                    errors.append(f"Task has no {field}")
            if not isinstance(image, str) or not image.strip():
                errors.append("Task has no pinned Docker image")
            elif image.strip().casefold() == "latest" or image.strip().casefold().endswith(":latest"):
                errors.append("Docker image uses the floating latest tag")
        except Exception as exc:
            errors.append(f"cannot parse/hash direct Harbor Task: {exc}")

    task = config.get("task") if isinstance(config.get("task"), dict) else {}
    entrypoints = {
        "instruction": (task.get("instruction"), "file"),
        "workspace": (task.get("workspace"), "directory"),
        "setup": (task.get("setup"), "file"),
        "test": (task.get("test"), "file"),
        "golden": (task.get("golden"), "file"),
    }
    for name, (relative, kind) in entrypoints.items():
        if not isinstance(relative, str) or not relative.strip():
            errors.append(f"task.toml [task].{name} is missing")
            continue
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            errors.append(f"task.toml [task].{name} escapes the Task root")
        elif kind == "file" and not target.is_file():
            errors.append(f"task.toml [task].{name} does not point to a delivered file")
        elif kind == "directory" and not target.is_dir():
            errors.append(f"task.toml [task].{name} does not point to a delivered directory")

    adapter = root / "environment" / "adapter.toml"
    if adapter.is_file():
        try:
            adapter_value = load_toml(adapter)
            for key in ("prepare", "validate", "run", "restore", "cleanup", "workspace"):
                relative = adapter_value.get(key)
                target = root / "environment" / str(relative) if relative else None
                if not target or not target.exists():
                    errors.append(f"environment/adapter.toml {key} entry is missing or unresolved")
        except Exception as exc:
            errors.append(f"invalid environment/adapter.toml: {exc}")

    source = root / "source.json"
    if source.is_file():
        try:
            data = json.loads(source.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("root is not an object")
            if data.get("task_id") not in (None, identity.get("task_id")):
                errors.append("source.json task_id conflicts with Task identity")
        except Exception as exc:
            errors.append(f"source.json exists but is invalid: {exc}")
    else:
        warnings.append("source.json is absent; this is allowed and does not block QC")

    testcase_manifest = root / "tests" / "required_testcases.json"
    testcase_count: int | None = None
    if testcase_manifest.is_file():
        try:
            rows = json.loads(testcase_manifest.read_text(encoding="utf-8-sig"))
            if not isinstance(rows, list):
                errors.append("tests/required_testcases.json must be a list")
            else:
                testcase_count = len(rows)
                if testcase_count < 5:
                    errors.append(
                        f"tests/required_testcases.json must contain at least 5 testcases; got {testcase_count}"
                    )
                elif testcase_count > 27:
                    warnings.append(
                        f"tests/required_testcases.json contains {testcase_count} testcases; "
                        "more than 27 requires manual scope review but does not block QC by itself"
                    )
        except Exception as exc:
            errors.append(f"cannot parse tests/required_testcases.json: {exc}")

    return {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "root": str(root),
        "task_root": str(root) if task_toml.is_file() else None,
        "task": identity,
        "task_config": config,
        "testcase_count": testcase_count,
        "format": "direct-harbor-task-with-jobs-v1",
    }
