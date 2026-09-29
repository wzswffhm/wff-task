#!/usr/bin/env python3
"""Preview the next project-level OBM task ID.

The ID format is YYYY-MM-DD-N. The date is local creation date, while N is a
project-wide sequence that never resets when the date changes.

This command does not reserve the ID. New task production must use
task_registry.py reserve so concurrent windows cannot receive the same ID.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


IGNORED_PARTS = {
    ".codex",
    ".git",
    ".venv",
    "Benchmark",
    "node_modules",
    "venv",
}


def next_id(root: Path, day: str) -> tuple[str, list[int]]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("date must use YYYY-MM-DD")
    pattern = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}-(\d+)(?!\d)")
    numbers: set[int] = set()
    if root.exists():
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if any(part in IGNORED_PARTS for part in relative.parts):
                continue
            numbers.update(int(match.group(1)) for match in pattern.finditer(path.name))
    value = max(numbers, default=0) + 1
    return f"{day}-{value}", sorted(numbers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    task_id, existing = next_id(args.root.expanduser().resolve(), args.date)
    if args.as_json:
        print(json.dumps({"task_id": task_id, "date": args.date, "existing_numbers": existing}))
    else:
        print(task_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
