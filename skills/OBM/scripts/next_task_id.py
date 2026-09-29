#!/usr/bin/env python3
"""Preview the next project-level OBM task ID for a local date.

The ID format is YYYY-MM-DD-N. Existing files and directories whose names
start with the date followed by a numeric component are counted, so a task
description may follow the number without changing the sequence.

This command does not reserve the ID. New task production must use
task_registry.py reserve so concurrent windows cannot receive the same ID.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def next_id(root: Path, day: str) -> tuple[str, list[int]]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("date must use YYYY-MM-DD")
    pattern = re.compile(rf"^{re.escape(day)}-(\d+)(?:$|[-_])")
    numbers: set[int] = set()
    if root.exists():
        for path in root.rglob("*"):
            match = pattern.match(path.name)
            if match:
                numbers.add(int(match.group(1)))
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
