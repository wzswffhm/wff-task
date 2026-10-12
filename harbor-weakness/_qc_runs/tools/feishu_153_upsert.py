# -*- coding: utf-8 -*-
"""FIN3-WKN-153 回传飞书作业表：新增一行 + 上传三个附件。

作业表坐标与字段 id 依据 `skills/harbor-weakness/references/09-feishu-worksheet-delivery.md`：
  base_token = QpzNb4fXSamfX6sLloBcPfHNnug
  table_id   = tblPNrBtjFfwOowN
可写字段：题目 fld1bfmLqv / 类型 fld6ND5UZL / 题目难度 fldYA4iRaD / 标注人 fldgADMj3N
          / 参考答案 fld2LBu2Ns / 考点信息 fldqj9Zstn / 做答思路 fld6ae02rH
不可写（甲方/质检侧）：序号 fld5kMM38p / 原工作表 fld1qchbC1 / 状态 fldKFzG0cA / 质检报告 fld92VdQU6
附件字段（走 +record-upload-attachment）：
  交付物 fld8TMUhqI / 题目附件信息 fldf8Ymaw2 / 标准答案附件信息 fld2TmGhqt

为什么用 Python 调 lark-cli 而不是 PowerShell：题面是 10 KB 中文长文本，
经 Windows 命令行 → shim 会破坏编码（见 09 文档 §2 警告）；Python subprocess 走
CreateProcessW（UTF-16），中文与长参数均安全。

用法:
  python feishu_153_upsert.py create          # 新增一行（题目/类型/难度/标注人），打印 record_id
  python feishu_153_upsert.py attach <rid>    # 向该行上传三个附件（在 TEMP 目录下执行以过路径白名单）
  python feishu_153_upsert.py get <rid>       # 读回该行，核对终态
"""
import json
import os
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

LARK = r"C:\nvm4w\nodejs\node_modules\@larksuite\cli\bin\lark-cli.exe"
BASE = "QpzNb4fXSamfX6sLloBcPfHNnug"
TABLE = "tblPNrBtjFfwOowN"
OPEN_ID = "ou_f4e4bc01ed9be1ef4cbaedcdf8f19d45"
USER_NAME = "wff"

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = H / "work_fin-b01_20261012-153" / "FIN3-WKN-153"
PKG = H / "_qc_runs" / "packages"
TMP = pathlib.Path(os.environ["TEMP"]) / "lark153"

F_TITLE = "fld1bfmLqv"      # 题目
F_TYPE = "fld6ND5UZL"       # 类型
F_DIFF = "fldYA4iRaD"       # 题目难度
F_OWNER = "fldgADMj3N"      # 标注人
F_REF = "fld2LBu2Ns"        # 参考答案
F_POINTS = "fldqj9Zstn"     # 考点信息（rubrics）
F_DELIV = "fld8TMUhqI"      # 交付物
F_TASKZIP = "fldf8Ymaw2"    # 题目附件信息
F_ANSWERZIP = "fld2TmGhqt"  # 标准答案附件信息

ATTACHMENTS = [
    (F_DELIV, "work_fin-b01_20261012-153.zip"),
    (F_TASKZIP, "FIN3-WKN-153_task.zip"),
    (F_ANSWERZIP, "FIN3-WKN-153_answer.zip"),
]


def run(args, cwd=None):
    env = {**os.environ, "LARK_CLI_NO_PROXY": "1"}
    r = subprocess.run([LARK, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd, env=env)
    return r


def jload(txt):
    i = txt.find("{")
    if i < 0:
        return None
    try:
        return json.loads(txt[i:])
    except Exception:
        return None


def plain(md: str) -> str:
    """题面 markdown -> 纯文本（仅去掉标题标记与强调符号，保留表格/列表可读性）。"""
    out = []
    for ln in md.splitlines():
        s = re.sub(r"^#{1,6}\s*", "", ln.rstrip())
        s = s.replace("**", "").replace("`", "")
        out.append(s)
    txt = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def cmd_create():
    title = plain((TASK / "instruction.md").read_text(encoding="utf-8"))
    fields = {
        F_TITLE: title,
        F_TYPE: ["weakness"],
        F_DIFF: ["A1"],                       # 三模型实测均分 0.675824 → A1
        F_OWNER: [{"id": OPEN_ID}],           # 标注人 = wff
    }
    r = run(["base", "+record-upsert", "--base-token", BASE, "--table-id", TABLE,
             "--json", json.dumps(fields, ensure_ascii=False), "--as", "user", "--format", "json"])
    print("rc =", r.returncode)
    print(r.stdout[-2500:] if r.stdout else "")
    if r.stderr.strip():
        print("[stderr]", r.stderr[-800:])
    d = jload(r.stdout or "")
    if d and d.get("ok"):
        rec = (d.get("data") or {}).get("record") or {}
        rid = rec.get("record_id") or (d.get("data") or {}).get("record_id")
        print("\n>>> record_id =", rid)
    return 0 if (d and d.get("ok")) else 1


def cmd_attach(rid):
    TMP.mkdir(parents=True, exist_ok=True)
    for f in PKG.glob("*.zip"):
        if f.name in [n for _fid, n in ATTACHMENTS]:
            dst = TMP / f.name
            if not dst.exists() or dst.stat().st_size != f.stat().st_size:
                dst.write_bytes(f.read_bytes())
    ok = True
    for fid, name in ATTACHMENTS:
        if not (TMP / name).is_file():
            print(f"[!!] 附件缺失: {TMP / name}")
            ok = False
            continue
        r = run(["base", "+record-upload-attachment", "--base-token", BASE, "--table-id", TABLE,
                 "--record-id", rid, "--field-id", fid, "--file", name,
                 "--as", "user", "--format", "json"], cwd=str(TMP))
        d = jload(r.stdout or "")
        good = bool(d and d.get("ok"))
        print(f"{'OK ' if good else 'FAIL'} {name} -> {fid} (rc={r.returncode})")
        if not good:
            print("     ", (r.stdout or r.stderr)[-400:])
            ok = False
    return 0 if ok else 1


def cmd_get(rid):
    r = run(["base", "+record-get", "--base-token", BASE, "--table-id", TABLE,
             "--record-id", rid, "--as", "user", "--format", "json"])
    d = jload(r.stdout or "")
    print("rc =", r.returncode, "ok =", bool(d and d.get("ok")))
    if not d:
        print((r.stdout or r.stderr)[-800:])
        return 1
    rec = (d.get("data") or {}).get("record") or {}
    fields = rec.get("fields") or {}
    names = {
        F_TITLE: "题目", F_TYPE: "类型", F_DIFF: "题目难度", F_OWNER: "标注人",
        F_REF: "参考答案", F_POINTS: "考点信息", F_DELIV: "交付物",
        F_TASKZIP: "题目附件信息", F_ANSWERZIP: "标准答案附件信息",
    }
    for fid, label in names.items():
        v = fields.get(fid)
        s = json.dumps(v, ensure_ascii=False)
        print(f"  {label:<14} {s[:220]}{'...' if len(s) > 220 else ''}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    action = sys.argv[1]
    if action == "create":
        raise SystemExit(cmd_create())
    if action == "attach":
        raise SystemExit(cmd_attach(sys.argv[2]))
    if action == "get":
        raise SystemExit(cmd_get(sys.argv[2]))
    print("未知动作:", action)
    raise SystemExit(2)
