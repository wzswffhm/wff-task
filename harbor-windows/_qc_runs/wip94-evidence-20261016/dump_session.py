# -*- coding: utf-8 -*-
"""按行号导出一个 DSH 会话的可见事件（用于人工核对造题时间线）。

用法：python dump_session.py <session-dir-name> <start> <end> [store]
"""
from __future__ import annotations

import io
import json
import pathlib
import sys

import zstandard

ROOT = pathlib.Path.home() / ".dsh" / "sessions"


def main() -> int:
    name = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    store = sys.argv[4] if len(sys.argv) > 4 else "--C-Users-Administrator-Desktop-wff-task--"
    path = next((ROOT / store / name).glob("*.jsonl.zstd"))
    dctx = zstandard.ZstdDecompressor()
    with path.open("rb") as fh, dctx.stream_reader(fh) as reader:
        text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        for index, line in enumerate(text):
            if index < start:
                continue
            if index > end:
                break
            try:
                obj = json.loads(line)
            except Exception:
                print(index, "RAW", line[:200])
                continue
            kind = obj.get("type")
            data = obj.get("data")
            blob = json.dumps(data, ensure_ascii=False)
            print(f"--- #{index} {kind} time={obj.get('time')}")
            print(blob[:900])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
