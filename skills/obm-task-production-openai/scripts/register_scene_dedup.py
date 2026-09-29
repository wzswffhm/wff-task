#!/usr/bin/env python3
"""Upsert one scene-dedup decision to Feishu and persist the verified result locally."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import task_registry


DEFAULT_CONFIG = Path("/Users/xiezhi/.codex/feishu-gsb.toml")
CONCLUSION_STATUS = {
    "distinct": "candidate",
    "high-risk": "rejected",
    "duplicate": "rejected",
}
CONFIG_VALUE_KEYS = {
    "distinct": "distinct",
    "high-risk": "high_risk",
    "duplicate": "duplicate",
}
FIELD_SPECS = {
    "core_scene": ("核心场景", "text"),
    "comparison": ("对比题面", "text"),
    "decision": ("去重判断", "select"),
    "rationale": ("判断依据", "text"),
    "annotator": ("标注员", "user"),
    "task_id": ("题目编号", "text"),
    "question": ("题面", "text"),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_toml_subset(path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse the string/bool subset used by the single OBM Feishu config."""
    sections: Dict[str, Dict[str, Any]] = {}
    current: Optional[str] = None
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is None or "=" not in line:
            raise ValueError("unsupported config syntax at {}:{}".format(path, line_number))
        key, raw_value = line.split("=", 1)
        value_text = raw_value.strip()
        if value_text.casefold() in {"true", "false"}:
            value: Any = value_text.casefold() == "true"
        else:
            try:
                value = ast.literal_eval(value_text)
            except (SyntaxError, ValueError) as exc:
                raise ValueError("unsupported config value at {}:{}".format(path, line_number)) from exc
        sections[current][key.strip()] = value
    return sections


def require_section(config: Dict[str, Dict[str, Any]], name: str) -> Dict[str, Any]:
    section = config.get(name)
    if not isinstance(section, dict):
        raise ValueError("missing config section [{}]".format(name))
    return section


def require_string(section: Dict[str, Any], key: str, section_name: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing {}.{}".format(section_name, key))
    return value.strip()


def run_cli(cli: str, args: Sequence[str], timeout: int = 60) -> Dict[str, Any]:
    # lark-cli emits UTF-8 on every platform; pin the decoder so a non-UTF-8
    # system locale does not turn its output into a UnicodeDecodeError.
    completed = subprocess.run(
        [cli, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError("lark-cli failed ({}): {}".format(completed.returncode, detail[-1500:]))
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("lark-cli did not return JSON") from exc
    if isinstance(result, dict) and result.get("ok") is False:
        raise RuntimeError("lark-cli returned an error: {}".format(json.dumps(result.get("error"), ensure_ascii=False)))
    return result


def nested_data(value: Dict[str, Any]) -> Dict[str, Any]:
    data = value.get("data")
    return data if isinstance(data, dict) else value


def first_value(value: Dict[str, Any], keys: Sequence[str]) -> Optional[Any]:
    for container in (value, nested_data(value)):
        for key in keys:
            if key in container:
                return container[key]
    return None


def verify_identity(cli: str, identity: Dict[str, Any]) -> Tuple[str, str]:
    result = run_cli(cli, ["auth", "status", "--json", "--verify"])
    expected_app = require_string(identity, "app_id", "identity")
    expected_open = require_string(identity, "open_id", "identity")
    if result.get("appId") != expected_app or result.get("verified") is not True:
        raise ValueError("Feishu app identity does not match the verified config")
    user = result.get("identities", {}).get("user", {})
    if user.get("available") is not True or user.get("verified") is not True:
        raise ValueError("verified Feishu user identity is unavailable")
    if user.get("openId") != expected_open:
        raise ValueError("Feishu user openId does not match the verified config")
    return expected_open, str(user.get("userName") or identity.get("display_name") or "verified user")


def verify_target(
    cli: str,
    target: Dict[str, Any],
    configured_fields: Dict[str, Any],
    configured_values: Dict[str, Any],
) -> Tuple[str, str, str, Dict[str, str], Dict[str, str]]:
    url = require_string(target, "url", "scene_dedup")
    expected_base = require_string(target, "base_token", "scene_dedup")
    expected_table = require_string(target, "table_id", "scene_dedup")
    expected_view = require_string(target, "view_id", "scene_dedup")
    resolved = run_cli(cli, ["base", "+url-resolve", "--url", url, "--as", "user", "--json"])
    actual_base = first_value(resolved, ["base_token", "baseToken", "app_token", "appToken"])
    actual_table = first_value(resolved, ["table_id", "tableId"])
    actual_view = first_value(resolved, ["view_id", "viewId"])
    if (actual_base, actual_table, actual_view) != (expected_base, expected_table, expected_view):
        raise ValueError("resolved scene-dedup target does not match the verified config")

    field_result = run_cli(
        cli,
        ["base", "+field-list", "--base-token", expected_base, "--table-id", expected_table, "--as", "user", "--json"],
    )
    field_items = nested_data(field_result).get("fields", [])
    by_id = {item.get("id"): item for item in field_items if isinstance(item, dict)}
    field_ids: Dict[str, str] = {}
    for key, (expected_name, expected_type) in FIELD_SPECS.items():
        field_id = require_string(configured_fields, key, "scene_dedup.fields")
        actual = by_id.get(field_id)
        if not actual or actual.get("name") != expected_name or actual.get("type") != expected_type:
            raise ValueError("scene-dedup field mismatch for {}".format(expected_name))
        field_ids[key] = field_id

    values = {
        conclusion: require_string(configured_values, config_key, "scene_dedup.values")
        for conclusion, config_key in CONFIG_VALUE_KEYS.items()
    }
    decision_field = by_id[field_ids["decision"]]
    available_options = {option.get("name") for option in decision_field.get("options", [])}
    missing_options = sorted(set(values.values()) - available_options)
    if missing_options:
        raise ValueError("scene-dedup select options are missing: {}".format(", ".join(missing_options)))
    return expected_base, expected_table, expected_view, field_ids, values


def load_entry(root: Path, reservation_id: str) -> Dict[str, Any]:
    registry_path, _ = task_registry.registry_paths(root)
    data = task_registry.load_registry(registry_path)
    matches = [entry for entry in data["entries"] if entry.get("reservation_id") == reservation_id]
    if len(matches) != 1:
        raise ValueError("reservation_id not found or is ambiguous")
    if matches[0].get("source") != "reservation":
        raise ValueError("scene-dedup registration requires a reserved task entry")
    return matches[0]


def parse_review(review_path: Path) -> Dict[str, Any]:
    text = review_path.read_text(encoding="utf-8")
    rationale = ""
    review_conclusion = ""
    comparisons: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("最终结论："):
            review_conclusion = line.split("：", 1)[1].strip()
        elif line.startswith("结论依据："):
            rationale = line.split("：", 1)[1].strip()
        elif line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and cells[0] not in {"最相近已有题", "已有题", "---", ""} and set(cells[0]) != {"-"}:
                comparisons.append(cells[0])
    return {
        "text": text,
        "rationale": rationale,
        "conclusion": review_conclusion,
        "comparisons": comparisons,
    }


def resolve_path(root: Path, value: Optional[Path], fallback: str) -> Path:
    path = value if value is not None else Path(fallback)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def read_optional_text(value: Optional[str], file_path: Optional[Path], root: Path) -> Optional[str]:
    if value and file_path:
        raise ValueError("provide text or file, not both")
    if value:
        return value.strip()
    if file_path:
        resolved = file_path.resolve() if file_path.is_absolute() else (root / file_path).resolve()
        return resolved.read_text(encoding="utf-8").strip()
    return None


def core_scene_from_profile(profile_path: Path) -> str:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    parts: List[str] = []
    goal = profile.get("scenario_goal")
    if isinstance(goal, str) and goal.strip():
        parts.append(goal.strip())
    for key in ("workflow", "state_and_lifecycle", "conflicts_failures_recovery", "observable_outcomes"):
        value = profile.get(key)
        if isinstance(value, list):
            parts.extend(str(item).strip() for item in value if str(item).strip())
    return " ".join(parts)


def matrix_records(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = nested_data(result)
    rows = data.get("data", [])
    fields = data.get("fields", [])
    record_ids = data.get("record_id_list", [])
    records = []
    for index, row in enumerate(rows):
        if index >= len(record_ids):
            break
        records.append({"record_id": record_ids[index], "fields": dict(zip(fields, row))})
    return records


def search_task_record(
    cli: str,
    base_token: str,
    table_id: str,
    field_ids: Dict[str, str],
    task_id: str,
) -> List[Dict[str, Any]]:
    args: List[str] = [
        "base", "+record-search", "--base-token", base_token, "--table-id", table_id,
        "--keyword", task_id, "--search-field", field_ids["task_id"],
    ]
    for field_id in field_ids.values():
        args.extend(["--field-id", field_id])
    args.extend(["--limit", "20", "--as", "user", "--format", "json"])
    records = matrix_records(run_cli(cli, args))
    return [record for record in records if record["fields"].get("题目编号") == task_id]


def read_record(
    cli: str,
    base_token: str,
    table_id: str,
    field_ids: Dict[str, str],
    record_id: str,
) -> Dict[str, Any]:
    args: List[str] = [
        "base", "+record-get", "--base-token", base_token, "--table-id", table_id,
        "--record-id", record_id,
    ]
    for field_id in field_ids.values():
        args.extend(["--field-id", field_id])
    args.extend(["--as", "user", "--format", "json"])
    records = matrix_records(run_cli(cli, args))
    if len(records) != 1:
        raise RuntimeError("failed to read back the Feishu scene-dedup record")
    return records[0]


def normalized_user_ids(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    ids = []
    for item in value:
        if isinstance(item, dict):
            candidate = item.get("id") or item.get("open_id") or item.get("openId")
            if candidate:
                ids.append(str(candidate))
    return ids


def verify_record(record: Dict[str, Any], expected: Dict[str, Any], open_id: str) -> None:
    fields = record["fields"]
    for name in ("题目编号", "核心场景", "对比题面", "判断依据", "题面"):
        if fields.get(name) != expected[name]:
            raise RuntimeError("Feishu read-back mismatch for {}".format(name))
    decision = fields.get("去重判断")
    if not isinstance(decision, list) or expected["去重判断"][0] not in decision:
        raise RuntimeError("Feishu read-back mismatch for 去重判断")
    if open_id not in normalized_user_ids(fields.get("标注员")):
        raise RuntimeError("Feishu read-back mismatch for 标注员")


def atomic_write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".{}-".format(path.name), suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, str(path))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def persist_registry_result(
    root: Path,
    reservation_id: str,
    conclusion: str,
    review_path: Path,
    local_record_path: Path,
    table_id: str,
    view_id: str,
    record_id: str,
    open_id: str,
    synced_at: str,
) -> Dict[str, Any]:
    with task_registry.locked_registry(root) as (_, data):
        matches = [entry for entry in data["entries"] if entry.get("reservation_id") == reservation_id]
        if len(matches) != 1:
            raise ValueError("reservation_id disappeared while registering scene dedup")
        entry = matches[0]
        entry["status"] = CONCLUSION_STATUS[conclusion]
        entry["dedup"] = {
            "conclusion": conclusion,
            "review_path": task_registry.project_relative(review_path, root),
            "local_record_path": task_registry.project_relative(local_record_path, root),
            "feishu_table_id": table_id,
            "feishu_view_id": view_id,
            "feishu_record_id": record_id,
            "annotator_open_id": open_id,
            "synced_at": synced_at,
        }
        entry["updated_at"] = synced_at
        return dict(entry)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reservation-id", required=True)
    parser.add_argument("--conclusion", choices=sorted(CONCLUSION_STATUS), required=True)
    parser.add_argument("--review-file", type=Path)
    parser.add_argument("--scene-profile", type=Path)
    parser.add_argument("--comparison", action="append", default=[])
    parser.add_argument("--core-scene")
    parser.add_argument("--core-scene-file", type=Path)
    parser.add_argument("--rationale")
    parser.add_argument("--rationale-file", type=Path)
    parser.add_argument("--question-text")
    parser.add_argument("--question-file", type=Path)
    parser.add_argument("--local-record", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    entry = load_entry(root, args.reservation_id)
    paths = entry.get("paths", {})
    work_path = str(paths.get("work") or Path("work") / str(entry["proposal_name"]))
    review_path = resolve_path(root, args.review_file, str(Path(work_path) / "scene-overlap-review.md"))
    if not review_path.is_file():
        raise ValueError("scene overlap review does not exist: {}".format(review_path))
    review = parse_review(review_path)
    review_conclusion = review.get("conclusion")
    if review_conclusion and review_conclusion not in {args.conclusion, args.conclusion.replace("-", "_")}:
        chinese_map = {"不重复": "distinct", "疑似重复": "high-risk", "重复": "duplicate"}
        normalized_review = chinese_map.get(review_conclusion, review_conclusion)
        if normalized_review != args.conclusion:
            raise ValueError("review conclusion does not match --conclusion")

    explicit_core_scene = read_optional_text(args.core_scene, args.core_scene_file, root)
    profile_core_scene = ""
    if args.scene_profile:
        profile_path = resolve_path(root, args.scene_profile, "")
        profile_core_scene = core_scene_from_profile(profile_path)
    core_scene = explicit_core_scene or profile_core_scene or str(entry.get("scene_summary", "")).strip()
    rationale = read_optional_text(args.rationale, args.rationale_file, root) or str(review.get("rationale", "")).strip()
    question = read_optional_text(args.question_text, args.question_file, root) or str(entry.get("scene_summary", "")).strip()
    comparisons = [item.strip() for item in args.comparison if item.strip()] or review.get("comparisons", [])
    if not core_scene or not rationale or not question or not comparisons:
        raise ValueError("core scene, comparison, rationale and question text must all be non-empty")
    comparison = "；".join(dict.fromkeys(comparisons))

    config = parse_toml_subset(args.config.expanduser().resolve())
    cli = require_string(require_section(config, "cli"), "path", "cli")
    identity = require_section(config, "identity")
    target = require_section(config, "scene_dedup")
    configured_fields = require_section(config, "scene_dedup.fields")
    configured_values = require_section(config, "scene_dedup.values")
    open_id, annotator_name = verify_identity(cli, identity)
    base_token, table_id, view_id, field_ids, option_values = verify_target(
        cli, target, configured_fields, configured_values
    )
    field_payload = {
        "核心场景": core_scene,
        "对比题面": comparison,
        "去重判断": [option_values[args.conclusion]],
        "判断依据": rationale,
        "标注员": [{"id": open_id}],
        "题目编号": str(entry["task_id"]),
        "题面": question,
    }
    existing = search_task_record(cli, base_token, table_id, field_ids, str(entry["task_id"]))
    if len(existing) > 1:
        raise ValueError("multiple Feishu scene-dedup records exist for {}".format(entry["task_id"]))
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "task_id": entry["task_id"],
            "conclusion": args.conclusion,
            "annotator": annotator_name,
            "existing_record_id": existing[0]["record_id"] if existing else None,
            "fields": {key: value for key, value in field_payload.items() if key != "标注员"},
        }, ensure_ascii=False, indent=2))
        return 0

    if existing:
        record_id = existing[0]["record_id"]
        body = {"update_records": {record_id: field_payload}}
        run_cli(cli, [
            "base", "+record-batch-update", "--base-token", base_token, "--table-id", table_id,
            "--json", json.dumps(body, ensure_ascii=False), "--as", "user", "--format", "json",
        ])
        operation = "updated"
    else:
        body = {"create_records": [field_payload]}
        run_cli(cli, [
            "base", "+record-batch-create", "--base-token", base_token, "--table-id", table_id,
            "--json", json.dumps(body, ensure_ascii=False), "--as", "user", "--format", "json",
        ])
        matches = search_task_record(cli, base_token, table_id, field_ids, str(entry["task_id"]))
        if len(matches) != 1:
            raise RuntimeError("could not uniquely find the newly created Feishu scene-dedup record")
        record_id = matches[0]["record_id"]
        operation = "created"

    read_back = read_record(cli, base_token, table_id, field_ids, record_id)
    verify_record(read_back, field_payload, open_id)
    synced_at = utc_now()
    default_local = Path(work_path) / "scene-dedup-record.json"
    local_record_path = resolve_path(root, args.local_record, str(default_local))
    local_record = {
        "schema_version": 1,
        "reservation_id": args.reservation_id,
        "task_id": entry["task_id"],
        "proposal_name": entry["proposal_name"],
        "conclusion": args.conclusion,
        "status": CONCLUSION_STATUS[args.conclusion],
        "review_path": task_registry.project_relative(review_path, root),
        "feishu": {
            "table_id": table_id,
            "view_id": view_id,
            "record_id": record_id,
            "annotator_open_id": open_id,
            "operation": operation,
            "verified_read_back": True,
        },
        "fields": field_payload,
        "synced_at": synced_at,
    }
    atomic_write_json(local_record_path, local_record)
    updated_entry = persist_registry_result(
        root, args.reservation_id, args.conclusion, review_path, local_record_path,
        table_id, view_id, record_id, open_id, synced_at,
    )
    print(json.dumps({
        "ok": True,
        "task_id": entry["task_id"],
        "conclusion": args.conclusion,
        "status": updated_entry["status"],
        "annotator": annotator_name,
        "feishu_record_id": record_id,
        "feishu_operation": operation,
        "local_record": task_registry.project_relative(local_record_path, root),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise SystemExit("error: {}".format(exc))
