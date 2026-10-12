# -*- coding: utf-8 -*-
"""submit_218.py —— 把 wfflab__wlogseg-218 交付包写入飞书「windwos作业」表。

口径（对照 215 / 216 的 submit_*_replace*.ps1，但 218 表内尚无行，故为**新建**）：

  * 新建一行：`文本` = 交付 zip 名；`标注员` = 当前 lark-cli 用户（wff）；
  * 上传三个附件字段：作业压缩包 / 分数截图 / oracle-nop截图；
  * **绝不写 `状态` 字段**（新建与上传前后都读回核对它没有被改动）。

用法：
    python submit_218.py            # 只做前置检查与 dry-run 打印
    python submit_218.py --confirm-write
    python submit_218.py --confirm-write --record-id recxxxx   # 续跑：行已建、只补附件
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CLI = r"E:\nvm\v24.3.0\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
WFF_OPEN_ID = "ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45"   # lark-cli auth status -> identities.user.openId

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
DELIV = ROOT / "deliverables" / "2026-10-12_wlogseg218-交付"
ZIP = DELIV / "package" / "wfflab__wlogseg-218-v1.0.0-delivery.zip"
IMG_SCORE = DELIV / "evidence" / "images" / "score_summary.png"
IMG_CTL = DELIV / "evidence" / "images" / "oracle_nop_controls.png"
RECEIPT = DELIV / "evidence" / "upload-218.json"

FIELD_TEXT = "fldffCZZex"        # 文本
FIELD_ASSIGNEE = "flda4emMz7"    # 标注员
FIELD_STATUS = "fldd6UxkAs"      # 状态（只读核对，不写）
FIELD_ZIP = "fldnki9xts"         # 作业压缩包
FIELD_SCORE_IMG = "fldg4yePGJ"   # 分数截图
FIELD_CTL_IMG = "fldZI4BCU2"     # oracle/nop截图

UPLOADS = [(FIELD_ZIP, "作业压缩包", ZIP),
           (FIELD_SCORE_IMG, "分数截图", IMG_SCORE),
           (FIELD_CTL_IMG, "oracle/nop截图", IMG_CTL)]


def run_cli(args, cwd=None):
    p = subprocess.run([CLI] + args, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        raise RuntimeError("lark-cli failed (%d): %s" % (p.returncode, raw[:800]))
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e < s:
        raise RuntimeError("invalid lark-cli JSON: %s" % raw[:800])
    return json.loads(raw[s:e + 1])


def cells_of(record_id: str) -> dict:
    r = run_cli(["base", "+record-get", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", record_id, "--format", "json"])
    fields = r["data"]["fields"]
    row = r["data"]["data"][0]
    return {fields[i]: (row[i] if i < len(row) else None) for i in range(len(fields))}


def find_existing(zip_name: str):
    r = run_cli(["base", "+record-list", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--limit", "200", "--format", "json",
                 "--field-id", FIELD_TEXT])
    rows = r["data"]["data"]
    rids = r["data"]["record_id_list"]
    for i, row in enumerate(rows):
        if row and str(row[0]) == zip_name:
            rid = rids[i]
            return rid.get("record_id") if isinstance(rid, dict) else rid
    return None


def att_str(cells, name):    v = cells.get(name)
    if not isinstance(v, list):
        return ""
    return ", ".join("%s(%s)" % (x.get("name"), x.get("size")) for x in v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm-write", action="store_true")
    ap.add_argument("--record-id", default="")
    a = ap.parse_args()

    for p in (ZIP, IMG_SCORE, IMG_CTL):
        if not p.is_file():
            raise SystemExit("缺文件：%s" % p)
    zip_name = ZIP.name
    print("zip        : %s (%d bytes)" % (zip_name, ZIP.stat().st_size))
    print("score img  : %s (%d bytes)" % (IMG_SCORE.name, IMG_SCORE.stat().st_size))
    print("ctl   img  : %s (%d bytes)" % (IMG_CTL.name, IMG_CTL.stat().st_size))

    record_id = a.record_id
    if not record_id:
        existed = find_existing(zip_name)
        if existed:
            record_id = existed
            print("已存在同名行：%s（不重复建行，走续跑路径）" % record_id)
        else:
            print("表内无 %s 对应行 → 将新建一行" % zip_name)

    if not a.confirm_write:
        print("\n[dry-run] 将执行：")
        if not record_id:
            print("  1) base +record-upsert（新建）：{\"文本\": %r, \"标注员\": [{\"id\": %r}]}"
                  % (zip_name, WFF_OPEN_ID))
        for fid, fname, path in UPLOADS:
            print("  2) base +record-upload-attachment --field-id %s --file %s  (%s)"
                  % (fid, path.name, fname))
        print("  3) base +record-get 读回校验（文本 / 标注员 / 三附件；状态只读不写）")
        print("\n加 --confirm-write 真正执行。")
        return 0

    if not record_id:
        created = run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
                           "--table-id", TABLE, "--format", "json", "--json",
                           json.dumps({"文本": zip_name,
                                       "标注员": [{"id": WFF_OPEN_ID}]},
                                      ensure_ascii=False)])
        blob = json.dumps(created, ensure_ascii=False)
        cand = created.get("data", {})
        record_id = (cand.get("record", {}) or {}).get("record_id") or cand.get("record_id")
        if not record_id:
            record_id = find_existing(zip_name)
        if not record_id:
            raise SystemExit("建行后未能取得 record_id：%s" % blob[:600])
        print("created    : record_id=%s" % record_id)

    before = cells_of(record_id)
    status_before = ",".join(map(str, before.get("状态") or [])) or "(empty)"
    print("status before : %s   (脚本不会修改它)" % status_before)

    # 先删旧、再传新：附件字段保持恰好 1 个文件（与 215/216 的替换口径一致）
    try:
        run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", record_id, "--format", "json",
                 "--json", json.dumps({name: [] for _, name, _ in UPLOADS},
                                      ensure_ascii=False)])
        print("cleared    : " + " / ".join(name for _, name, _ in UPLOADS))
    except Exception as e:  # noqa: BLE001
        print("clear 警告（将直接追加）：%s" % e)

    for fid, fname, path in UPLOADS:
        run_cli(["base", "+record-upload-attachment", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", record_id,
                 "--field-id", fid, "--file", path.name, "--format", "json"],
                cwd=path.parent)
        print("uploaded   : %s <- %s" % (fname, path.name))

    after = cells_of(record_id)
    status_after = ",".join(map(str, after.get("状态") or [])) or "(empty)"
    text_ok = str(after.get("文本")) == zip_name
    who = after.get("标注员") or []
    assignee_ids = [x.get("id") for x in who] if isinstance(who, list) else []
    assignee_ok = WFF_OPEN_ID in assignee_ids
    att_ok = {}
    for fid, fname, path in UPLOADS:
        got = after.get(fname) or []
        att_ok[fname] = any(x.get("name") == path.name and int(x.get("size") or 0) == path.stat().st_size
                            for x in got)
    status_untouched = status_before == status_after

    receipt = {
        "record_id": record_id,
        "table_id": TABLE,
        "base_token": BASE,
        "uploaded_at": datetime.now().astimezone().isoformat(),
        "round": "initial delivery (opus x3 completed on 4router.net)",
        "text_field": zip_name,
        "assignee": {"id": WFF_OPEN_ID, "name": "wff"},
        "status_before": status_before,
        "status_after": status_after,
        "status_untouched": status_untouched,
        "attachments": {
            fname: {"field_id": fid, "name": path.name, "size": path.stat().st_size,
                    "local_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "verified": att_ok[fname]}
            for fid, fname, path in UPLOADS},
        "readback": {"text_ok": text_ok, "assignee_ok": assignee_ok,
                     "status_untouched": status_untouched},
        "rounds": rounds_from_jobs(),
        "executed_by": "_qc_runs/wlogseg-build/submit_218.py --confirm-write",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))

    ok = text_ok and assignee_ok and status_untouched and all(att_ok.values())
    if not ok:
        print("\n!! 读回校验未全过：text=%s assignee=%s status_untouched=%s attachments=%s"
              % (text_ok, assignee_ok, status_untouched, att_ok))
        return 1
    print("\nSECTION_OK  回执写入 %s" % RECEIPT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
