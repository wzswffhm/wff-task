# -*- coding: utf-8 -*-
"""先看清 DSH 会话行的结构，再决定怎么提取造题时间线。"""
from __future__ import annotations

import io
import json
import pathlib

import zstandard

ROOT = pathlib.Path.home() / ".dsh" / "sessions" / "--C-Users-Administrator-Desktop-wff-task--"
NAME = "f3653368-39bc-41cb-ac57-e727296f6ae2"


def main() -> int:
    path = next(ROOT.glob(f"{NAME}/*.jsonl.zstd"))
    dctx = zstandard.ZstdDecompressor()
    with path.open("rb") as fh, dctx.stream_reader(fh) as reader:
        text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        for index, line in enumerate(text):
            if index > 8:
                break
            try:
                obj = json.loads(line)
            except Exception:
                print(index, "RAW", line[:200])
                continue
            print(index, "keys:", sorted(obj.keys()))
            for key in ("kind", "type", "role", "ts", "timestamp", "name", "tool"):
                if key in obj:
                    print("     ", key, "=", str(obj[key])[:120])
            for key in ("text", "content", "message", "observation", "input", "arguments"):
                if key in obj:
                    value = obj[key]
                    print("     ", key, "=", json.dumps(value, ensure_ascii=False)[:300])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
