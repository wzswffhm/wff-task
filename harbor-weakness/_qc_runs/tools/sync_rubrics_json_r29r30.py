# -*- coding: utf-8 -*-
"""把 tests/rubrics.toml 的 R29/R30 description 同步到设计态 rubrics.json。

质检项 #1 要求两文件判据文本一致；本轮收紧了 R29/R30 满分锚点，两处需同步。
保持 JSON 原有缩进/编码风格。
"""
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150")
TOML = W / "tests" / "rubrics.toml"
JSON = W / "rubrics.json"
TARGETS = ["R29", "R30"]
DRY = "--dry-run" in sys.argv


def toml_desc():
    txt = TOML.read_text(encoding="utf-8")
    out = {}
    blocks = re.split(r"\[\[criterion\]\]", txt)[1:]
    for b in blocks:
        mid = re.search(r'^\s*id\s*=\s*"([^"]+)"', b, re.M)
        md = re.search(r'^\s*description\s*=\s*"((?:[^"\\]|\\.)*)"', b, re.M | re.S)
        if mid and md:
            raw = md.group(1)
            # TOML 基本字符串转义：\" -> " ，\\ -> \
            desc = raw.replace('\\"', '"').replace("\\\\", "\\")
            out[mid.group(1)] = desc
    return out


def main():
    tdesc = toml_desc()
    j = json.loads(JSON.read_text(encoding="utf-8"))
    items = j["items"]
    changed = 0
    for cid in TARGETS:
        td = tdesc[cid]
        for it in items:
            if it.get("id") == cid:
                jd = it.get("description", "")
                same = jd == td
                print(f"[{cid}] 一致={same}  json_len={len(jd)} toml_len={len(td)}")
                if not same:
                    changed += 1
                    if not DRY:
                        it["description"] = td
                break
    if changed and not DRY:
        # 保持原格式：先探测缩进
        raw = JSON.read_text(encoding="utf-8")
        indent = 2 if raw.lstrip().startswith("{\n  ") else None
        JSON.write_text(json.dumps(j, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
        print(f"\n已更新 {changed} 条 -> {JSON}")
    elif not changed:
        print("\n无需更新")
    else:
        print("\n[dry-run] 不写入")

    # 复检
    j2 = json.loads(JSON.read_text(encoding="utf-8"))
    for cid in TARGETS:
        for it in j2["items"]:
            if it.get("id") == cid:
                print(f"复检 [{cid}]: json==toml -> {it['description'] == tdesc[cid]}")


if __name__ == "__main__":
    main()
