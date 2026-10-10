# -*- coding: utf-8 -*-
"""序号 239 复检整改（FIN3-WKN-150 / fix6）飞书回写。

  题目附件信息   fldf8Ymaw2 <- FIN3-WKN-150_task.zip
  标准答案附件信息 fld2TmGhqt <- FIN3-WKN-150_answer.zip
  交付物信息     fld8TMUhqI <- work_fin-b01_20261006_fix6-150.zip（先删全部旧包，保证单一附件）

不动字段：状态 fldKFzG0cA（仍「待返修」）、难度 fldYA4iRaD（维持 A1）。

用法：
  python feishu_writeback_fix6_150.py            # 干跑，只读 + 包内自检
  python feishu_writeback_fix6_150.py --apply    # 实际执行
"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT = "QpzNb4fXSamfX6sLloBcPfHNnug"
TB = "tblPNrBtjFfwOowN"
REC = "reczz28Jf9pZeD1T"
H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

BATCH = H / "work_fin-b01_20261006_fix6-150.zip"
TASKZ = H / "FIN3-WKN-150_task.zip"
ANSZ = H / "FIN3-WKN-150_answer.zip"

TARGETS = [
    ("题目附件信息", "fldf8Ymaw2", TASKZ, "same-name"),
    ("标准答案附件信息", "fld2TmGhqt", ANSZ, "same-name"),
    ("交付物", "fld8TMUhqI", BATCH, "all"),
]

APPLY = "--apply" in sys.argv
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args, yes=False, cwd=None):
    cmd = [LARK] + list(args)
    if yes:
        cmd.append("--yes")
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, cwd=cwd)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def read_row():
    rc, out, err = lark("base", "+record-list", "--base-token", BT, "--table-id", TB,
                        "--page-size", "100", "--as", "user", "--format", "json")
    dd = json.loads(out)["data"]
    idx = {n: i for i, n in enumerate(dd["fields"])}
    return dd, idx, dd["data"][dd["record_id_list"].index(REC)]


def atts_of(dd, idx, row, fname):
    v = row[idx[fname]]
    return v if isinstance(v, list) else []


def pkg_selfcheck():
    """包内自检：逐条对应复检报告第 4/5 条与归档口径。"""
    print("=== 包内自检 ===")
    ok = True
    bz = zipfile.ZipFile(BATCH)
    infos = {i.filename: i for i in bz.infolist()}
    names = set(infos)

    # 第 5 条：.sh 权限 0755
    for rel in ("work_fin-b01_20261006_fix6-150/FIN3-WKN-150/solution/solve.sh",
                "work_fin-b01_20261006_fix6-150/FIN3-WKN-150/tests/test.sh"):
        m = infos[rel].external_attr >> 16
        good = (m & 0o777) == 0o755
        ok &= good
        print(f'  [{"OK" if good else "!!"}] 批次包 {rel.split("/")[-1]} 权限={oct(m & 0o777)}（应 0o755）')

    # 第 4 条：金标桥接表含"加：非经常性损益"
    for rel in ("work_fin-b01_20261006_fix6-150/FIN3-WKN-150/solution/golden_output/"
                "FIN3-WKN-150_PreIPO投资决策备忘录.md",
                "work_fin-b01_20261006_fix6-150/FIN3-WKN-150/tests/__golden_output/"
                "FIN3-WKN-150_PreIPO投资决策备忘录.md"):
        md = bz.read(rel).decode("utf-8")
        hit = "加：非经常性损益（税后）" in md and "24,740" in md and "22,190" not in md
        ok &= hit
        print(f'  [{"OK" if hit else "!!"}] 金标备忘录（{rel.split("/")[-2]}）：'
              f'含"加：非经常性损益（税后）"={"加：非经常性损益（税后）" in md}  '
              f'24,740 保留={"24,740" in md}  无 22,190={"22,190" not in md}')

    # 归档与禁入项
    checks = {
        "含 交付文档.md": any(n.endswith("FIN3-WKN-150/交付文档.md") for n in names),
        "含 跑分产物与轨迹/summary.json": any(n.endswith("跑分产物与轨迹/summary.json") for n in names),
        "含四执行体 reward.json": sum(n.endswith("/reward.json") for n in names) == 4,
        "无 _rejudge 残留": not any("_rejudge" in n for n in names),
        "无 __pycache__ 残留": not any("__pycache__" in n for n in names),
        "第二层唯一 FIN3-WKN-150": all(
            n.split("/")[1] == "FIN3-WKN-150" for n in names if n.count("/") >= 1 and n.split("/")[1]),
    }
    for k, v in checks.items():
        ok &= bool(v)
        print(f'  [{"OK" if v else "!!"}] {k}')

    # task / answer 包
    with zipfile.ZipFile(TASKZ) as tz:
        ti = {i.filename: (i.external_attr >> 16) & 0o777 for i in tz.infolist()}
        tsh = ti.get("FIN3-WKN-150/tests/test.sh")
        rj = json.loads(tz.read("FIN3-WKN-150/rubrics.json").decode("utf-8"))
        n_items = len(rj.get("items") or [])
        g = (tsh == 0o755) and n_items == 36
        ok &= g
        print(f'  [{"OK" if g else "!!"}] task 包：tests/test.sh={oct(tsh) if tsh else None}  '
              f'rubrics.json items={n_items}（应 36）')
    with zipfile.ZipFile(ANSZ) as az:
        ai = {i.filename: (i.external_attr >> 16) & 0o777 for i in az.infolist()}
        ssh = ai.get("FIN3-WKN-150/solution/solve.sh")
        g = ssh == 0o755
        ok &= g
        print(f'  [{"OK" if g else "!!"}] answer 包：solution/solve.sh={oct(ssh) if ssh else None}')
    return ok


def main():
    print(f"模式: {'APPLY（实际写入）' if APPLY else 'DRY-RUN（只读）'}\n")
    missing = [str(f) for _, _, f, _ in TARGETS if not f.exists()]
    if missing:
        print("[ERR] 待传文件不存在:")
        for m in missing:
            print("   ", m)
        return 1
    for _, _, f, _ in TARGETS:
        print(f"  待传 {f.name}: {f.stat().st_size:,} B")
    print()
    if not pkg_selfcheck():
        print("\n[ERR] 包内自检未通过，停止。")
        return 1

    dd, idx, row = read_row()
    print("\n=== 上传前 ===")
    for fname, fid, path, mode in TARGETS:
        atts = atts_of(dd, idx, row, fname)
        print(f"  [{fname}] {fid}  附件数={len(atts)}  删除策略={mode}")
        for a in atts:
            print(f"     - {a.get('name')}  size={a.get('size')}  token={a.get('file_token')}")
    st = row[idx.get("状态")] if "状态" in idx else None
    df = row[idx.get("题目难度")] if "题目难度" in idx else None
    print(f"  [不动] 状态={st!r}   题目难度={df!r}")

    if not APPLY:
        print("\n（DRY-RUN 结束；加 --apply 执行写入）")
        return 0

    for fname, fid, path, mode in TARGETS:
        dd, idx, row = read_row()
        atts = atts_of(dd, idx, row, fname)
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
                            "--file", path.name, "--as", "user", "--format", "json",
                            cwd=str(H))
        print(f"  [上传] {fname} {path.name} rc={rc}  {(out or err)[:160]}")

    dd, idx, row = read_row()
    print("\n=== 上传后 ===")
    ok = True
    for fname, fid, path, mode in TARGETS:
        atts = atts_of(dd, idx, row, fname)
        hit = [a for a in atts if a.get("size") == path.stat().st_size]
        print(f"  [{fname}] 附件数={len(atts)}")
        for a in atts:
            flag = "✅ 本次新包" if a.get("size") == path.stat().st_size else "⚠ 其他"
            print(f'     - {a.get("name")}  size={a.get("size")}  {flag}')
        if len(atts) != 1 or not hit:
            ok = False
            print(f"     [ERR] 期望恰好 1 个且为 size={path.stat().st_size} 的新包")
    st = row[idx.get("状态")] if "状态" in idx else None
    df = row[idx.get("题目难度")] if "题目难度" in idx else None
    print(f"  [复核] 状态={st!r}   题目难度={df!r}")
    print("\n结论:", "全部字段终态正确 ✅" if ok else "存在字段未达预期 ⚠")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
