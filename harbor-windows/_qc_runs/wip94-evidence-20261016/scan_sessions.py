# -*- coding: utf-8 -*-
"""在 DSH 会话存档里定位造题会话。

输出每个会话第一次提到隐藏套件 / 候选包的行号与片段，用来找出
“作者写测试”的那次会话，并确定首次写入测试文件的时间点。
"""
from __future__ import annotations

import io
import json
import pathlib

import zstandard

ROOT = pathlib.Path.home() / ".dsh" / "sessions" / "--C-Users-Administrator-Desktop-wff-task--"
KEYS = ("test_wvas_semantics.py", "test_wsparse_semantics.py",
        "wfflab__wvas-216", "wfflab__wsparse-215")


def peek(line: str) -> str:
    try:
        obj = json.loads(line)
    except Exception:
        return line[:160]
    kind = obj.get("kind") or obj.get("type") or "?"
    ts = obj.get("ts") or obj.get("timestamp") or ""
    text = obj.get("text") or obj.get("content") or ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    return f"{kind} {ts} :: {text[:140]}"


def main() -> int:
    files = sorted(ROOT.rglob("*.jsonl.zstd"))
    print("sessions:", len(files))
    for path in files:
        dctx = zstandard.ZstdDecompressor()
        first: dict[str, tuple[int, str]] = {}
        total = 0
        with path.open("rb") as fh, dctx.stream_reader(fh) as reader:
            text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
            for index, line in enumerate(text):
                total = index
                for key in KEYS:
                    if key in line and key not in first:
                        first[key] = (index, peek(line))
        if first:
            print("=" * 78)
            print(path.parent.name, f"lines={total + 1}")
            for key, (index, snippet) in first.items():
                print(f"  {key} @line {index}: {snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
