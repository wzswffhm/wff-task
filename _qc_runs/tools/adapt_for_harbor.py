"""Apply auditable Harbor-compatibility adaptations to staged task copies.

The delivered packages target a bespoke runner (environment/adapter.toml,
schema "outside-harbor-adapter-v1"): [task] carries runner paths, [environment]
omits os/docker_image, and entrypoints are PowerShell .ps1 while harbor only
discovers solve.bat / test.bat on Windows.

Every adaptation is recorded so the QC report can attribute failures either to
the delivered package or to the QC harness adaptation layer.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IMAGE = {
    "wfflab__wfmt-215": "outside-harbor/wfflab__wfmt-215:1.0",
}


def set_env_keys(text: str, pairs: dict[str, str]) -> tuple[str, list[str]]:
    """Insert missing keys right after the [environment] header."""
    notes: list[str] = []
    header = re.search(r"(?m)^\[environment\][ \t]*\r?\n", text)
    if not header:
        raise ValueError("[environment] section not found")
    block_start = header.end()
    block_end = re.search(r"(?m)^\[", text[block_start:])
    block = text[block_start: block_start + (block_end.start() if block_end else len(text))]
    inserts: list[str] = []
    for key, value in pairs.items():
        if re.search(rf"(?m)^\s*{re.escape(key)}\s*=", block):
            continue
        inserts.append(f"{key} = {value}")
        notes.append(f"[environment].{key} = {value}")
    if inserts:
        text = text[:block_start] + "\n".join(inserts) + "\n" + text[block_start:]
    return text, notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()

    record: list[dict] = []
    for task_dir in sorted(p for p in args.staged.iterdir() if (p / "task.toml").is_file()):
        task_id = task_dir.name
        config = task_dir / "task.toml"
        text = config.read_text(encoding="utf-8")
        notes: list[str] = []

        pairs = {"os": '"windows"', "workdir": '"C:\\\\testbed"'}
        # 215's Dockerfile already copies workspace/ into C:/testbed and a
        # prebuilt image of exactly that Dockerfile exists, so reuse it.
        # 217's Dockerfile is image-only (the supplier runner bind-mounts the task
        # tree at C:\\task), so harbor must build it and the QC adaptation layer
        # has to inject the workspace the way 215's Dockerfile already does.
        if IMAGE.get(task_id):
            pairs["docker_image"] = f'"{IMAGE[task_id]}"'
        text, added = set_env_keys(text, pairs)
        notes.extend(added)

        dockerfile = task_dir / "environment" / "Dockerfile"
        if dockerfile.is_file():
            body = dockerfile.read_text(encoding="utf-8")
            if "COPY" not in body.upper() or "testbed" not in body:
                body = body.rstrip("\n") + (
                    "\n\n# QC adaptation: harbor runs the task from an image, not from a\n"
                    "# bind-mounted task tree, so the candidate workspace must be baked in.\n"
                    'COPY ["workspace/", "C:/testbed/"]\n'
                )
                dockerfile.write_text(body, encoding="utf-8", newline="")
                notes.append("environment/Dockerfile: appended COPY workspace/ -> C:/testbed/")

        config.write_text(text, encoding="utf-8", newline="")
        record.append({"task_id": task_id, "file": "task.toml", "adaptations": notes})

    args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
