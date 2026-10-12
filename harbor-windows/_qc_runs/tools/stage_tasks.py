"""Stage harbor-windows task packages for local QC without touching the originals.

Only one adaptation is applied: harbor's TaskConfig requires ``[task].name``.
The delivered packages declare ``[task].id`` instead, so the standard CLI cannot
discover them at all. Every adaptation is recorded in adaptations.json so the
QC report can separate package defects from QC harness adaptations.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


def find_tasks(root: Path) -> list[Path]:
    root = root.resolve()
    if (root / "task.toml").is_file():
        return [root]
    return sorted({p.parent for p in root.rglob("task.toml")
                   if not any(part.startswith(".") for part in p.parent.relative_to(root).parts)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", action="append", default=None)
    args = parser.parse_args()

    tasks = find_tasks(args.input)
    if args.only:
        wanted = set(args.only)
        tasks = [t for t in tasks if t.name in wanted]
    if not tasks:
        print("no tasks found", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    record: list[dict] = []
    for task in tasks:
        stage = args.out / task.name
        if stage.exists():
            shutil.rmtree(stage)
        shutil.copytree(task, stage)
        config = stage / "task.toml"
        text = config.read_text(encoding="utf-8")
        entry = {"task_id": task.name, "staged": str(stage), "adaptations": []}
        if not re.search(r"(?m)^\s*name\s*=", text.split("[task]", 1)[-1] if "[task]" in text else ""):
            if "[task]" in text:
                replacement = '\\1name = "' + task.name.replace("__", "/") + '"\n'
                text = re.sub(r"(?m)^(\[task\][ \t]*\r?\n)", replacement, text, count=1)
                config.write_text(text, encoding="utf-8", newline="")
                entry["adaptations"].append({
                    "file": "task.toml",
                    "change": ('inserted name = "' + task.name.replace("__", "/") +
                               '" into [task] (harbor TaskConfig requires org/name)'),
                })
        record.append(entry)
    (args.out / "adaptations.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
