# -*- coding: utf-8 -*-
"""宽松扫描：找出真正在“造题”的会话（而不是在讨论已有题包）。

对每个会话统计造题特征词的出现次数与会话起止时间。
"""
from __future__ import annotations

import io
import json
import pathlib

import zstandard

ROOT = pathlib.Path.home() / ".dsh" / "sessions"
MARKERS = (
    "FSCTL_SET_SPARSE", "FSCTL_QUERY_ALLOCATED_RANGES", "preallocate",
    "VirtualQueryEx", "GetMappedFileNameW", "MEMORY_BASIC_INFORMATION",
    "required_testcases.json", "judge.toml", "instruction.md",
    "windows_mechanism.json", "orgate", "oracle",
)


def main() -> int:
    for store in sorted(ROOT.iterdir()):
        if not store.is_dir():
            continue
        for path in sorted(store.rglob("*.jsonl.zstd")):
            counts = {m: 0 for m in MARKERS}
            first_time = last_time = None
            lines = 0
            dctx = zstandard.ZstdDecompressor()
            with path.open("rb") as fh, dctx.stream_reader(fh) as reader:
                text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
                for line in text:
                    lines += 1
                    for marker in MARKERS:
                        if marker in line:
                            counts[marker] += 1
                    if first_time is None:
                        try:
                            first_time = json.loads(line).get("time")
                        except Exception:
                            pass
                    try:
                        last_time = json.loads(line).get("time") or last_time
                    except Exception:
                        pass
            if counts["preallocate"] or counts["VirtualQueryEx"]:
                hot = {k: v for k, v in counts.items() if v}
                print(f"{store.name}/{path.parent.name}  lines={lines}")
                print(f"    {hot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
