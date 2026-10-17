# -*- coding: utf-8 -*-
"""解析 r3/raw/*.json（lark-cli base +record-get 输出），导出返修原因与附件元数据。

lark-cli 的 record-get 返回结构：
  data.fields = 字段名数组
  data.data   = 行数组，每行的值数组与 fields 按位置一一对应
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
RAW = HERE / "raw"

PKGS = {
    "wsparse-215": "reczz28KwEOO3xHy",
    "wvas-216": "reczz28KQU8reW2k",
    "wcancel-219": "reczz28N2IGu9XmA",
    "wciocp-220": "reczz28NUOrl6Foj",
}

WATCH = ("状态", "甲方ID", "Qwen分数", "opus分数", "glm分数", "Kimi分数",
         "作业压缩包", "返修原因", "分数截图", "oracle/nop截图", "质检通过截图")


def plain(value):
    """把飞书富文本/文件数组压成可读文本。"""
    if value is None:
        return None
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            if "file_token" in value[0]:
                return [{"name": v.get("name"), "size": v.get("size"),
                         "file_token": v.get("file_token")} for v in value]
            return [v.get("text", v.get("name", str(v))) for v in value]
        return value
    if isinstance(value, str):
        text = re.sub(r"<br\s*/?>", "\n", value)
        text = re.sub(r"</?(b|strong|u|i|em|p|div|span)[^>]*>", "", text)
        return text
    return value


def main() -> int:
    out = {}
    for key, rid in PKGS.items():
        raw = json.loads((RAW / f"{key}.json").read_text(encoding="utf-8"))
        payload = raw["data"]
        fields = payload["fields"]
        row = payload["data"][0]
        rec = {"record_id": rid}
        for name, value in zip(fields, row):
            if name in WATCH:
                rec[name] = plain(value)
        rec["all_field_names"] = list(fields)
        out[key] = rec

    (HERE / "wff-records-r3.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 飞书 4 条记录最新快照（r3）", ""]
    for key in PKGS:
        rec = out[key]
        att = rec.get("作业压缩包") or []
        lines += [f"## {key}", "",
                  f"- record_id: `{rec['record_id']}`",
                  f"- 状态: {rec.get('状态')}",
                  f"- 甲方ID: {rec.get('甲方ID')}",
                  f"- Qwen / opus: {rec.get('Qwen分数')} / {rec.get('opus分数')}",
                  f"- 作业压缩包: " + ("; ".join(
                      f"`{a['name']}` {a['size']} B token={a['file_token']}" for a in att) or "（空）"),
                  f"- 分数截图: " + ("; ".join(
                      f"{a['name']} {a['size']} B" for a in (rec.get('分数截图') or [])) or "（空）"),
                  "",
                  "### 返修原因全文", "", "```text",
                  (rec.get("返修原因") or "").strip(), "```", ""]
    (HERE / "wff-reasons-r3.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for key in PKGS:
        rec = out[key]
        att = rec.get("作业压缩包") or []
        print(f"{key}: 状态={rec.get('状态')} 甲方ID={rec.get('甲方ID')} "
              f"zip={[(a['name'], a['size']) for a in att]} "
              f"返修原因长度={len(rec.get('返修原因') or '')}")
    print("field names:", sorted(out["wsparse-215"]["all_field_names"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
