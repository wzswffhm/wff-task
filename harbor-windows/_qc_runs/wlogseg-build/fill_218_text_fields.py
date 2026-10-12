# -*- coding: utf-8 -*-
"""fill_218_text_fields.py —— 补齐 218 飞书行的三个文本字段（对齐 215/216 口径）。

  * `题目方向`：`<方向族>/<语言>/<任务类型>`，与 215（LEB128 varint + CRC32 容器）、
    216（二进制容器格式）同一体例，但按 218 的真实机制描述；
  * `甲方ID`  ：交付 zip 文件名（215/216 同字段即其 zip 名）；
  * `提示词`  ：题包 instruction.md 原文（215/216 同字段为各自 instruction.md）。

**不写 `状态`**，写入前后读回核对它没有变化。

用法：
    python fill_218_text_fields.py [--confirm-write]
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

CLI = r"E:\nvm\v24.3.0\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
RECORD_ID = "reczz28MRVnWkD2v"     # 本轮新建的 218 行

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wlogseg-218-v1.0.0-delivery"
INSTRUCTION = PKG / "instruction.md"
RECEIPT = ROOT / "deliverables" / "2026-10-12_wlogseg218-交付" / "evidence" / "upload-218.json"

DIRECTION = ("Windows/文件格式与序列化（分段追加日志容器：8 字节索引条目 + 8 字节段对齐 + "
             "标准 CRC-32 + truncated/structure 错误分类）/Python/缺陷修复")


def run_cli(args):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    raw = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        raise RuntimeError("lark-cli failed (%d): %s" % (p.returncode, raw[:800]))
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e < s:
        raise RuntimeError("invalid lark-cli JSON: %s" % raw[:800])
    return json.loads(raw[s:e + 1])


def cells() -> dict:
    r = run_cli(["base", "+record-get", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", RECORD_ID, "--format", "json"])
    fields = r["data"]["fields"]
    row = r["data"]["data"][0]
    return {fields[i]: (row[i] if i < len(row) else None) for i in range(len(fields))}


def flat(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "".join(x.get("text", "") for x in v if isinstance(x, dict)) or str(v)
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-write", action="store_true")
    a = ap.parse_args()

    prompt = INSTRUCTION.read_text(encoding="utf-8")
    payload = {"题目方向": DIRECTION, "甲方ID": PKG.name + ".zip", "提示词": prompt}
    print("record   : %s" % RECORD_ID)
    print("题目方向 : %s" % DIRECTION)
    print("甲方ID   : %s" % payload["甲方ID"])
    print("提示词   : %d 字符（来自 %s）" % (len(prompt), INSTRUCTION.name))

    before = cells()
    st_before = ",".join(map(str, before.get("状态") or [])) or "(empty)"
    print("status before: %s   (不会修改)" % st_before)

    if not a.confirm_write:
        print("\n[dry-run] 将执行 base +record-upsert --record-id %s --json {题目方向, 甲方ID, 提示词}"
              % RECORD_ID)
        return 0

    run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
             "--table-id", TABLE, "--record-id", RECORD_ID, "--format", "json",
             "--json", json.dumps(payload, ensure_ascii=False)])

    after = cells()
    st_after = ",".join(map(str, after.get("状态") or [])) or "(empty)"
    checks = {
        "题目方向": flat(after.get("题目方向")) == DIRECTION,
        "甲方ID": flat(after.get("甲方ID")) == payload["甲方ID"],
        "提示词": flat(after.get("提示词")) == prompt,
        "状态未改动": st_before == st_after,
    }
    print(json.dumps({"status_before": st_before, "status_after": st_after,
                      "checks": checks}, ensure_ascii=False, indent=2))

    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        rec["text_fields"] = {"题目方向": DIRECTION, "甲方ID": payload["甲方ID"],
                              "提示词_chars": len(prompt),
                              "verified": checks, "note": "状态字段仍未写入、未改动"}
        RECEIPT.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print("回执已更新：%s" % RECEIPT)

    ok = all(checks.values())
    print("TEXT_FIELDS_OK" if ok else "!! 文本字段校验未全过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
