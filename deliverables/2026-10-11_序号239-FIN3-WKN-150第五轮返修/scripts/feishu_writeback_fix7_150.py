# -*- coding: utf-8 -*-
"""序号 239 第五轮 fix7 飞书附件回写。"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BASE_TOKEN = "QpzNb4fXSamfX6sLloBcPfHNnug"
TABLE_ID = "tblPNrBtjFfwOowN"
RECORD_ID = "reczz28Jf9pZeD1T"
H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH_ZIP = H / "work_fin-b01_20261006_fix7-150.zip"
TASK_ZIP = H / "FIN3-WKN-150_task.zip"
ANSWER_ZIP = H / "FIN3-WKN-150_answer.zip"
TARGETS = [
    ("题目附件信息", "fldf8Ymaw2", TASK_ZIP, "same-name"),
    ("标准答案附件信息", "fld2TmGhqt", ANSWER_ZIP, "same-name"),
    ("交付物", "fld8TMUhqI", BATCH_ZIP, "all"),
]
APPLY = "--apply" in sys.argv
ENV = dict(os.environ)
ENV["LARK_CLI_NO_PROXY"] = "1"


def lark(*args: str, yes: bool = False, cwd: pathlib.Path | None = None):
    command = [LARK, *args]
    if yes:
        command.append("--yes")
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", env=ENV, cwd=cwd)
    return result.returncode, result.stdout or "", result.stderr or ""


def read_row():
    code, out, err = lark("base", "+record-list", "--base-token", BASE_TOKEN,
                          "--table-id", TABLE_ID, "--page-size", "100", "--as", "user",
                          "--format", "json")
    if code:
        raise SystemExit(err or out)
    data = json.loads(out)["data"]
    index = {name: position for position, name in enumerate(data["fields"])}
    row = data["data"][data["record_id_list"].index(RECORD_ID)]
    return data, index, row


def attachments(row, index, field):
    value = row[index[field]]
    return value if isinstance(value, list) else []


def selfcheck() -> bool:
    print("=== package self-check ===")
    ok = True
    with zipfile.ZipFile(BATCH_ZIP) as archive:
        infos = {info.filename: info for info in archive.infolist()}
        names = set(infos)
        root = BATCH_ZIP.stem
        for rel in (f"{root}/FIN3-WKN-150/solution/solve.sh",
                    f"{root}/FIN3-WKN-150/tests/test.sh"):
            mode = (infos[rel].external_attr >> 16) & 0o777
            passed = mode == 0o755
            ok &= passed
            print(f'  [{"OK" if passed else "!!"}] {rel.split("/")[-1]}={oct(mode)}')
        for rel in (f"{root}/FIN3-WKN-150/solution/golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md",
                    f"{root}/FIN3-WKN-150/tests/__golden_output/FIN3-WKN-150_PreIPO投资决策备忘录.md"):
            memo = archive.read(rel).decode("utf-8")
            passed = ("退出回报测算与信息边界" in memo and "参数以外的假设不得自行引入" in memo
                      and "待核实" in memo and "条件分析" in memo)
            ok &= passed
            print(f'  [{"OK" if passed else "!!"}] {rel.split("/")[-2]} 退出口径修订')
        rubric = archive.read(f"{root}/FIN3-WKN-150/tests/rubrics.toml").decode("utf-8")
        passed = "退出回报口径披露正确" in rubric and "如按 2029 年上市" not in rubric
        ok &= passed
        print(f'  [{"OK" if passed else "!!"}] R27 新口径')
        checks = {
            "version=1.0.7": b'version = "1.0.7"' in archive.read(f"{root}/FIN3-WKN-150/task.toml"),
            "summary mean gate": b'"mean": 0.' in archive.read(f"{root}/FIN3-WKN-150/跑分产物与轨迹/summary.json"),
            "four rewards": sum(name.endswith("/reward.json") for name in names) == 4,
            "no rejudge": not any("_rejudge" in name or "__pycache__" in name for name in names),
            "single second-level": all(name.split("/")[1] == "FIN3-WKN-150"
                                       for name in names if name.count("/") >= 1 and name.split("/")[1]),
        }
        for label, passed in checks.items():
            ok &= passed
            print(f'  [{"OK" if passed else "!!"}] {label}')

    with zipfile.ZipFile(TASK_ZIP) as archive:
        info = {item.filename: (item.external_attr >> 16) & 0o777 for item in archive.infolist()}
        rubric = json.loads(archive.read("FIN3-WKN-150/rubrics.json"))
        passed = info.get("FIN3-WKN-150/tests/test.sh") == 0o755 and len(rubric["items"]) == 36
        ok &= passed
        print(f'  [{"OK" if passed else "!!"}] task zip test.sh/items')
    with zipfile.ZipFile(ANSWER_ZIP) as archive:
        info = {item.filename: (item.external_attr >> 16) & 0o777 for item in archive.infolist()}
        passed = info.get("FIN3-WKN-150/solution/solve.sh") == 0o755
        ok &= passed
        print(f'  [{"OK" if passed else "!!"}] answer zip solve.sh')
    return ok


def main() -> int:
    print(f"mode={'APPLY' if APPLY else 'DRY-RUN'}")
    missing = [str(path) for _, _, path, _ in TARGETS if not path.exists()]
    if missing:
        print("missing files:")
        for path in missing:
            print(" ", path)
        return 1
    for _, _, path, _ in TARGETS:
        print(f"  pending {path.name}: {path.stat().st_size:,} B")
    if not selfcheck():
        print("self-check failed")
        return 1

    data, index, row = read_row()
    print("=== before upload ===")
    for field, field_id, path, mode in TARGETS:
        items = attachments(row, index, field)
        print(f"  {field}: count={len(items)} mode={mode}")
        for item in items:
            print(f"    - {item.get('name')} size={item.get('size')}")
    print(f"  unchanged state={row[index.get('状态')]!r} difficulty={row[index.get('题目难度')]!r}")
    if not APPLY:
        print("DRY-RUN complete")
        return 0

    for field, field_id, path, mode in TARGETS:
        data, index, row = read_row()
        for item in attachments(row, index, field):
            if mode == "same-name" and item.get("name") != path.name:
                print(f"  keep {field} {item.get('name')}")
                continue
            code, out, err = lark("base", "+record-remove-attachment", "--base-token", BASE_TOKEN,
                                  "--table-id", TABLE_ID, "--record-id", RECORD_ID,
                                  "--field-id", field_id, "--file-token", item["file_token"],
                                  "--as", "user", "--format", "json", yes=True)
            print(f"  remove {field} {item.get('name')} rc={code}")
        code, out, err = lark("base", "+record-upload-attachment", "--base-token", BASE_TOKEN,
                              "--table-id", TABLE_ID, "--record-id", RECORD_ID,
                              "--field-id", field_id, "--file", path.name, "--as", "user",
                              "--format", "json", cwd=str(H))
        print(f"  upload {field} {path.name} rc={code} {(out or err)[:160]}")

    data, index, row = read_row()
    print("=== after upload ===")
    passed = True
    for field, field_id, path, mode in TARGETS:
        items = attachments(row, index, field)
        exact = [item for item in items if item.get("size") == path.stat().st_size]
        print(f"  {field}: count={len(items)}")
        for item in items:
            print(f"    - {item.get('name')} size={item.get('size')}")
        if len(items) != 1 or not exact:
            passed = False
    print(f"  state={row[index.get('状态')]!r} difficulty={row[index.get('题目难度')]!r}")
    print("result:", "PASS" if passed else "FAIL")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
