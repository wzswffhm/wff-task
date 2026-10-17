# -*- coding: utf-8 -*-
"""找出真正写入隐藏套件 / 候选包的会话事件，用于 VV-24 / VV-25 / VV-35 证据。

只统计“写入类”事件（write_file / create_file / edit_file / apply_patch），
按会话和首次写入时间排序，输出会话 id、事件序号、时间与文件路径。
"""
from __future__ import annotations

import io
import json
import pathlib
import re

import zstandard

ROOT = pathlib.Path.home() / ".dsh" / "sessions" / "--C-Users-Administrator-Desktop-wff-task--"
WRITE_HINTS = ("write_file", "create_file", "edit_file", "apply_patch", "write_text",
               "multi_edit", "str_replace")
TARGETS = ("test_wvas_semantics.py", "test_wsparse_semantics.py")

PATH_RE = re.compile(r'"path"\s*:\s*"([^"]{0,160})"')
CMD_RE = re.compile(r'"command"\s*:\s*"([^"]{0,160})"')


def main() -> int:
    rows = []
    for path in sorted(ROOT.rglob("*.jsonl.zstd")):
        dctx = zstandard.ZstdDecompressor()
        with path.open("rb") as fh, dctx.stream_reader(fh) as reader:
            text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
            for index, line in enumerate(text):
                if not any(t in line for t in TARGETS):
                    continue
                if not any(h in line for h in WRITE_HINTS):
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                blob = json.dumps(obj.get("data"), ensure_ascii=False)
                paths = PATH_RE.findall(blob)
                hits = [p for p in paths if any(t.split(".")[0] in p for t in TARGETS)]
                rows.append((path.parent.name, index, obj.get("time", ""),
                             obj.get("type", ""), hits[:4] or paths[:4]))
    print("write-ish events touching the hidden suites:", len(rows))
    for name, index, when, kind, hits in rows:
        print(f"{name}  #{index:<6} {when}  {kind:<16} {hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
