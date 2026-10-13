# -*- coding: utf-8 -*-
"""feishu_probe.py -- 只读检查飞书「windwos作业」表里 218/219 两行的状态。

不写入任何内容。

用法：
    python feishu_probe.py
"""
from __future__ import annotations

import json
import subprocess
import sys

CLI = r"E:\nvm\v24.3.0\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
FIELD_TEXT = "fldffCZZex"

TARGETS = [
    "wfflab__wlogseg-218-v1.1.0-delivery.zip",
    "wfflab__wpeimg-219-v1.1.0-delivery.zip",
    "wfflab__wlogseg-218-v1.0.0-delivery.zip",
]


def run_cli(args):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    raw = (p.stdout or "") + (p.stderr or "")
    s, e = raw.find("{"), raw.rfind("}")
    if p.returncode != 0 or s < 0:
        raise RuntimeError("lark-cli failed (%d): %s" % (p.returncode, raw[:800]))
    return json.loads(raw[s:e + 1])


def main() -> int:
    r = run_cli(["base", "+record-list", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--limit", "200", "--format", "json"])
    fields = r["data"]["fields"]
    rows = r["data"]["data"]
    rids = r["data"]["record_id_list"]
    print("fields:", fields)
    print("rows  :", len(rows))
    idx = {name: i for i, name in enumerate(fields)}
    ti = idx.get("文本")
    si = idx.get("状态")
    ai = idx.get("标注员")
    zi = idx.get("作业压缩包")
    for i, row in enumerate(rows):
        text = str(row[ti]) if ti is not None and row[ti] else ""
        if not any(t in text for t in TARGETS):
            continue
        rid = rids[i]
        rid = rid.get("record_id") if isinstance(rid, dict) else rid
        status = row[si] if si is not None else None
        who = row[ai] if ai is not None else None
        att = row[zi] if zi is not None else None
        names = ", ".join("%s(%s)" % (a.get("name"), a.get("size"))
                          for a in (att or []) if isinstance(a, dict))
        print("-" * 70)
        print("record_id :", rid)
        print("text      :", text)
        print("status    :", status)
        print("assignee  :", [w.get("name") for w in (who or []) if isinstance(w, dict)])
        print("zip field :", names or "(empty)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
