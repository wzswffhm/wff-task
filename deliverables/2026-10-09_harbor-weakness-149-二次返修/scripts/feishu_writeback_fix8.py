# -*- coding: utf-8 -*-
"""2026-10-09 二次返修飞书回写：
  题目附件信息   fldf8Ymaw2 <- FIN3-WKN-149_task.zip
  标准答案附件信息 fld2TmGhqt <- FIN3-WKN-149_answer.zip
  交付物信息     fld8TMUhqI <- work_fin-b01_20261009_fix8-149.zip（先删旧 fix7 包，保证单一附件）

用法：
  python feishu_writeback_fix8.py            # 干跑，只读不写
  python feishu_writeback_fix8.py --apply    # 实际执行
"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')

LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT = "QpzNb4fXSamfX6sLloBcPfHNnug"
TB = "tblPNrBtjFfwOowN"
REC = "rec28himvkSA77"
H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

TARGETS = [
    ("题目附件信息", "fldf8Ymaw2", H / "FIN3-WKN-149_task.zip", "same-name"),
    ("标准答案附件信息", "fld2TmGhqt", H / "FIN3-WKN-149_answer.zip", "same-name"),
    ("交付物", "fld8TMUhqI", H / "work_fin-b01_20261009_fix8-149.zip", "all"),
]

APPLY = "--apply" in sys.argv
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args, yes=False):
    cmd = [LARK] + list(args)
    if yes:
        cmd.append("--yes")
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def read_row():
    rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                        "--page-size", "100", "--as", "user", "--format", "json")
    dd = json.loads(out)["data"]
    idx = {n: i for i, n in enumerate(dd["fields"])}
    return dd, idx, dd["data"][dd["record_id_list"].index(REC)]


def field_attachments(dd, idx, row, fname):
    v = row[idx[fname]]
    return v if isinstance(v, list) else []


def main():
    print(f"模式: {'APPLY（实际写入）' if APPLY else 'DRY-RUN（只读）'}\n")
    missing = [str(f) for _, _, f, _ in TARGETS if not f.exists()]
    if missing:
        print('[ERR] 待传文件不存在:')
        for m in missing:
            print('   ', m)
        return 1
    for _, _, f, _ in TARGETS:
        print(f'  待传 {f.name}: {f.stat().st_size:,} B')

    # 包内自检（fix8 关键改动是否在包里）
    tz = zipfile.ZipFile(H / "FIN3-WKN-149_task.zip")
    rules = tz.read("FIN3-WKN-149/environment/input_files/rules_windows.csv").decode("utf-8")
    j = json.loads(tz.read("FIN3-WKN-149/rubrics.json").decode("utf-8"))
    print(f'\n  包内 rules_windows.csv: 含「累计收益为负」={"累计收益为负" in rules}  '
          f'含「不少于 20 个」={"不少于 20 个" in rules}')
    print(f'  包内 rubrics.json: 条目={len(j["items"])}  '
          f'scoring.v_definition={"v_definition" in (j.get("metadata", {}).get("scoring") or {})}')
    bz = zipfile.ZipFile(H / "work_fin-b01_20261009_fix8-149.zip")
    names = bz.namelist()
    print(f'  批次包: {len(names)} 条目，含 FIN3-WKN-149/交付文档.md = '
          f'{any(n.endswith("FIN3-WKN-149/交付文档.md") for n in names)}，'
          f'含 跑分产物= {any("跑分产物与轨迹/summary.json" in n for n in names)}')

    dd, idx, row = read_row()
    print('\n=== 上传前 ===')
    for fname, fid, path, mode in TARGETS:
        atts = field_attachments(dd, idx, row, fname)
        print(f'  [{fname}] {fid}  附件数={len(atts)}  删除策略={mode}')
        for a in atts:
            print(f'     - {a.get("name")}  size={a.get("size")}  token={a.get("file_token")}')

    if not APPLY:
        print('\n（DRY-RUN 结束；加 --apply 执行写入）')
        return 0

    for fname, fid, path, mode in TARGETS:
        dd, idx, row = read_row()
        atts = field_attachments(dd, idx, row, fname)
        for a in atts:
            if mode == "same-name" and a.get("name") != path.name:
                print(f'  [跳过] {fname} 保留非同名的 {a.get("name")}')
                continue
            rc, out, err = lark("base", "+record-remove-attachment", "--base-token", BT,
                                "--table-id", TB, "--record-id", REC, "--field-id", fid,
                                "--file-token", a["file_token"], "--as", "user",
                                "--format", "json", yes=True)
            print(f'  [删除] {fname} {a.get("name")}({a.get("size")}B) rc={rc}')
        rc, out, err = lark("base", "+record-upload-attachment", "--base-token", BT,
                            "--table-id", TB, "--record-id", REC, "--field-id", fid,
                            "--file", str(path), "--as", "user", "--format", "json")
        print(f'  [上传] {fname} {path.name} rc={rc}  {(out or err)[:160]}')

    dd, idx, row = read_row()
    print('\n=== 上传后 ===')
    ok = True
    for fname, fid, path, mode in TARGETS:
        atts = field_attachments(dd, idx, row, fname)
        print(f'  [{fname}] 附件数={len(atts)}')
        hit = [a for a in atts if a.get("size") == path.stat().st_size]
        for a in atts:
            flag = '✅ 本次新包' if a.get("size") == path.stat().st_size else '⚠ 其他'
            print(f'     - {a.get("name")}  size={a.get("size")}  {flag}')
        if not hit:
            ok = False
            print(f'     [ERR] 未找到 size={path.stat().st_size} 的新包')
    print('\n结论:', '全部字段终态正确 ✅' if ok else '存在字段未达预期 ⚠')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
