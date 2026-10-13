# -*- coding: utf-8 -*-
"""submit_delivery.py -- 把 wfflab__wlogseg-218 / wfflab__wpeimg-219 的交付包写回飞书。

口径（对齐 215/216 的替换流程）：
  * 只写 `文本`、四个分数列、三个附件列；**绝不写 `状态` 字段**（上传前后读回核对）；
  * 附件「先清空旧、再传新」，每个附件字段保持恰好 1 个文件；
  * 行不存在时新建（219 首轮）；存在时按 record_id 续跑替换（218 返修）。

用法：
    python submit_delivery.py --task 218
    python submit_delivery.py --task 218 --confirm-write
    python submit_delivery.py --task 219 --confirm-write --record-id recXXXX
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import sys
from pathlib import Path

CLI = r"E:\nvm\v24.3.0\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "EsJebL8JJaf7g4sIbItcnMFgnvg"
TABLE = "tblRDxcGkblflMBA"
WFF_OPEN_ID = "ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45"

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"

TASKS = {
    "218": {
        "pkg": "wfflab__wlogseg-218-v1.1.0-delivery",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wlogseg218-返修",
        "sequence": ["qwen", "opus", "glm", "kimi"],
    },
    "219": {
        "pkg": "wfflab__wpeimg-219-v1.4.0-delivery",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wpeimg219-返修",
        "sequence": ["qwen", "opus", "glm", "kimi"],
    },
}

# Field IDs are authoritative: the table's display names are inconsistent
# (e.g. "opus分数" is lowercase while "Qwen分数"/"Kimi分数" are not).
FIELD_TEXT = "文本"
FIELD_ASSIGNEE = "标注员"
FIELD_STATUS = "状态"
FIELD_ZIP = "作业压缩包"
FIELD_SCORE_IMG = "分数截图"
FIELD_CTL_IMG = "oracle/nop截图"
FIELD_IDS = {
    "文本": "fldffCZZex",
    "标注员": "flda4emMz7",
    "状态": "fldd6UxkAs",
    "作业压缩包": "fldnki9xts",
    "分数截图": "fldg4yePGJ",
    "oracle/nop截图": "fldZI4BCU2",
    "Qwen分数": "fld4L6XW9p",
    "opus分数": "fldlid4pGC",
    "glm分数": "fldU9Zv4o6",
    "Kimi分数": "fldvkmPVpM",
}
SCORE_FIELDS = {"qwen": "Qwen分数", "opus": "opus分数", "glm": "glm分数", "kimi": "Kimi分数"}


def by_id(payload: dict) -> dict:
    """Translate display names to field ids for writes."""
    out = {}
    for name, value in payload.items():
        fid = FIELD_IDS.get(name)
        if not fid:
            raise KeyError("no field id registered for %r" % name)
        out[fid] = value
    return out


def run_cli(args, cwd=None):
    p = subprocess.run([CLI] + args, cwd=str(cwd) if cwd else None,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        raise RuntimeError("lark-cli failed (%d): %s" % (p.returncode, raw[:800]))
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e < s:
        raise RuntimeError("invalid lark-cli JSON: %s" % raw[:600])
    return json.loads(raw[s:e + 1])


def cells_of(record_id: str) -> dict:
    r = run_cli(["base", "+record-get", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", record_id, "--format", "json"])
    fields = r["data"]["fields"]
    row = r["data"]["data"][0]
    return {fields[i]: (row[i] if i < len(row) else None) for i in range(len(fields))}


def find_existing(text: str):
    r = run_cli(["base", "+record-list", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--limit", "200", "--format", "json",
                 "--field-id", FIELD_IDS["文本"]])
    rows = r["data"]["data"]
    rids = r["data"]["record_id_list"]
    for i, row in enumerate(rows):
        if row and str(row[0]) == text:
            rid = rids[i]
            return rid.get("record_id") if isinstance(rid, dict) else rid
    return None


def score_strings(task: str, cfg: dict) -> dict:
    """Build the per-model score cells from the assembled jobs."""
    pkg = REL / "staged" / cfg["pkg"]
    report = pkg / "jobs" / "_index" / "assembly_report.json"
    if not report.is_file():
        return {}
    doc = json.loads(report.read_text(encoding="utf-8-sig"))
    rows = doc.get("jobs", [])
    out = {}
    for alias, field in SCORE_FIELDS.items():
        rs = [r for r in rows if r["kind"] == "model" and str(r["job"]).startswith("model-%s-" % alias)]
        rs = [r for r in rs if not r.get("invalid_reason")]
        if rs:
            out[field] = "%d/%d" % (sum(int(r["score"] or 0) for r in rs), len(rs))
    return out


def att_names(cells, name):
    v = cells.get(name)
    if not isinstance(v, list):
        return []
    return ["%s(%s)" % (x.get("name"), x.get("size")) for x in v if isinstance(x, dict)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--confirm-write", action="store_true")
    ap.add_argument("--record-id", default="")
    a = ap.parse_args()
    cfg = TASKS[a.task]

    zip_path = cfg["deliverable"] / "package" / (cfg["pkg"] + ".zip")
    img_score = cfg["deliverable"] / "evidence" / "images" / "score_summary.png"
    img_ctl = cfg["deliverable"] / "evidence" / "images" / "oracle_nop_controls.png"
    for p in (zip_path, img_score, img_ctl):
        if not p.is_file():
            raise SystemExit("缺文件：%s" % p)
    zip_name = zip_path.name
    # lark-cli rejects a --file value containing a path separator, and the
    # "oracle/nop截图" field's display name is passed through to the uploaded
    # file name. Upload under a separator-free name so the attachment lands.
    def safe_name(path: Path) -> str:
        return path.name.replace("/", "-").replace("\\", "-")

    uploads = [(FIELD_ZIP, "作业压缩包", zip_path),
               (FIELD_SCORE_IMG, "分数截图", img_score),
               (FIELD_CTL_IMG, "oracle/nop截图", img_ctl)]
    scores = score_strings(a.task, cfg)

    print("task       : %s" % a.task)
    print("zip        : %s (%d bytes)" % (zip_name, zip_path.stat().st_size))
    print("score img  : %s (%d bytes)" % (img_score.name, img_score.stat().st_size))
    print("ctl   img  : %s (%d bytes)" % (img_ctl.name, img_ctl.stat().st_size))
    print("score cells: %s" % json.dumps(scores, ensure_ascii=False))

    record_id = a.record_id
    if not record_id:
        record_id = find_existing(zip_name)
    if not record_id and a.task == "218":
        record_id = "reczz28MRVnWkD2v"      # the v1.0.0 row being replaced
        print("218: 复用既有行（v1.0.0 → v1.1.0 替换）record_id=%s" % record_id)
    print("record_id  : %s" % (record_id or "(将新建)"))

    payload_text = {"文本": zip_name, **scores}
    if not a.confirm_write:
        print("\n[dry-run] 将执行：")
        if not record_id:
            print("  1) +record-upsert 新建：%s" % json.dumps(
                by_id({**payload_text, FIELD_ASSIGNEE: [{"id": WFF_OPEN_ID}]}), ensure_ascii=False))
        else:
            print("  1) +record-upsert 更新：%s" % json.dumps(by_id(payload_text), ensure_ascii=False))
        for fid, fname, path in uploads:
            print("  2) +record-upload-attachment --field-id %s --file %s (%s)"
                  % (fid, path.name, fname))
        print("  3) +record-get 读回校验（文本/分数/三附件；状态只读不写）")
        print("\n加 --confirm-write 真正执行。")
        return 0

    if not record_id:
        created = run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
                           "--table-id", TABLE, "--format", "json", "--json",
                           json.dumps(by_id({**payload_text,
                                             FIELD_ASSIGNEE: [{"id": WFF_OPEN_ID}]}),
                                      ensure_ascii=False)])
        cand = created.get("data", {})
        record_id = (cand.get("record", {}) or {}).get("record_id") or cand.get("record_id")
        if not record_id:
            record_id = find_existing(zip_name)
        if not record_id:
            raise SystemExit("建行后未能取得 record_id：%s" % json.dumps(created)[:500])
        print("created    : record_id=%s" % record_id)

    before = cells_of(record_id)
    status_before = ",".join(map(str, before.get(FIELD_STATUS) or [])) or "(empty)"
    print("status before : %s   (脚本不会修改它)" % status_before)

    # text + scores (written by field id)
    run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
             "--table-id", TABLE, "--record-id", record_id, "--format", "json",
             "--json", json.dumps(by_id(payload_text), ensure_ascii=False)])
    print("updated    : 文本 + 分数列")

    # clear then upload, so each attachment field holds exactly one file
    try:
        run_cli(["base", "+record-upsert", "--as", "user", "--base-token", BASE,
                 "--table-id", TABLE, "--record-id", record_id, "--format", "json",
                 "--json", json.dumps({FIELD_IDS[name]: [] for _, name, _ in uploads},
                                      ensure_ascii=False)])
        print("cleared    : " + " / ".join(name for _, name, _ in uploads))
    except Exception as exc:  # noqa: BLE001
        print("clear 警告（将直接追加）：%s" % exc)

    for fid, fname, path in uploads:
        upload_name = safe_name(path)
        if upload_name != path.name:
            staged = path.parent / upload_name
            if staged.exists() and staged.resolve() != path.resolve():
                staged.unlink()
            if not staged.exists():
                import shutil as _shutil
                _shutil.copy2(path, staged)
            src_name, src_dir = upload_name, path.parent
        else:
            src_name, src_dir = path.name, path.parent
        # Back-to-back attachment uploads occasionally answer 404 on the third
        # call; retry a few times with a short pause before giving up.
        last_error = None
        for attempt in range(1, 5):
            try:
                run_cli(["base", "+record-upload-attachment", "--as", "user",
                         "--base-token", BASE, "--table-id", TABLE,
                         "--record-id", record_id, "--field-id", fid,
                         "--file", src_name, "--format", "json"],
                        cwd=src_dir)
                last_error = None
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                print("upload retry %d/4 for %s: %s"
                      % (attempt, fname, str(exc).splitlines()[-1][:90]))
                time.sleep(2 * attempt)
        if last_error is not None:
            raise SystemExit("upload failed for %s after 4 attempts: %s"
                             % (fname, last_error))
        print("uploaded   : %s <- %s" % (fname, src_name))

    after = cells_of(record_id)
    status_after = ",".join(map(str, after.get(FIELD_STATUS) or [])) or "(empty)"
    text_ok = str(after.get(FIELD_TEXT)) == zip_name
    who = after.get(FIELD_ASSIGNEE) or []
    assignee_ok = WFF_OPEN_ID in [x.get("id") for x in who if isinstance(x, dict)]
    scores_ok = all(str(after.get(k)) == v for k, v in scores.items())
    att_ok = {}
    for _fid, fname, path in uploads:
        names = att_names(after, fname)
        att_ok[fname] = len(names) == 1 and str(path.stat().st_size) in names[0]

    print("\n--- readback ---")
    print("文本          : %s  ok=%s" % (after.get(FIELD_TEXT), text_ok))
    print("标注员        : %s  ok=%s" % ([x.get("name") for x in who if isinstance(x, dict)], assignee_ok))
    print("状态 before/after: %s -> %s  untouched=%s"
          % (status_before, status_after, status_before == status_after))
    for k in sorted(scores):
        print("%-13s : %s" % (k, after.get(k)))
    for _fid, fname, _p in uploads:
        print("%-13s : %s  ok=%s" % (fname, att_names(after, fname), att_ok[fname]))

    receipt = {
        "task": a.task, "record_id": record_id, "zip": zip_name,
        "zip_sha256": (zip_path.parent / (zip_name + ".sha256")).read_text().strip().split()[0]
        if (zip_path.parent / (zip_name + ".sha256")).is_file() else None,
        "scores": {k: after.get(k) for k in scores},
        "status_before": status_before, "status_after": status_after,
        "readback": {"text_ok": text_ok, "assignee_ok": assignee_ok,
                     "scores_ok": scores_ok, "attachments_ok": att_ok},
        "executed_by": "logs/submit_delivery.py --confirm-write",
    }
    out = cfg["deliverable"] / "evidence" / ("upload-%s.json" % a.task)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\n回执写入 %s" % out)

    ok = text_ok and assignee_ok and status_before == status_after and scores_ok and all(att_ok.values())
    print("SECTION_%s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
