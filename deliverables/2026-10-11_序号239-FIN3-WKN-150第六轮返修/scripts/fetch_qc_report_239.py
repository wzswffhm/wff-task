# -*- coding: utf-8 -*-
"""下载序号 239 记录上的最新「质检报告」附件，并导出全部关键字段到 JSON。"""
import json
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT = "QpzNb4fXSamfX6sLloBcPfHNnug"
TB = "tblPNrBtjFfwOowN"
REC = "reczz28Jf9pZeD1T"
ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables"
                    r"\2026-10-11_序号239-FIN3-WKN-150第六轮返修")
EVID = ROOT / "evidence"
EVID.mkdir(parents=True, exist_ok=True)

env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args: str):
    p = subprocess.run([LARK] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def main() -> int:
    rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                        "--page-size", "100", "--as", "user", "--format", "json")
    if rc != 0:
        print("record-list failed", rc, err[:400])
        return 1
    dd = json.loads(out)["data"]
    idx = {n: i for i, n in enumerate(dd["fields"])}
    row = dd["data"][dd["record_id_list"].index(REC)]

    (EVID / "record_snapshot.json").write_text(
        json.dumps({n: row[i] for n, i in idx.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print("=== 记录关键字段 ===")
    for key in ["序号", "题目难度", "状态", "标注人", "题目附件信息",
                "标准答案附件信息", "交付物", "质检报告"]:
        if key not in idx:
            continue
        val = row[idx[key]]
        if isinstance(val, list) and val and isinstance(val[0], dict):
            val = " | ".join(f'{a.get("name")}({a.get("size")}B)' for a in val)
        print(f"  {key:12s}: {str(val)[:160]}")

    atts = row[idx["质检报告"]]
    atts = atts if isinstance(atts, list) else []
    print(f"\n=== 质检报告附件（{len(atts)} 个）===")
    for att in atts:
        name, tok = att.get("name"), att.get("file_token")
        dst = EVID / name
        rc, out, err = lark("base", "+record-download-attachment", "--base-token", BT,
                            "--table-id", TB, "--record-id", REC, "--file-token", tok,
                            "--output", str(dst), "--as", "user", "--format", "json")
        print(f"  {name}: rc={rc} exists={dst.exists()} "
              f"size={dst.stat().st_size if dst.exists() else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
