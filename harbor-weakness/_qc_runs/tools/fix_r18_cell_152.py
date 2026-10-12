# -*- coding: utf-8 -*-
"""R18 兜底：description 中所有『单元格』改为『格位』（双文件同步），
清除 check_rubric_style --strict 的表格类定位语 FAIL。"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
JSONF = TASK / "rubrics.json"
TOML = TASK / "tests" / "rubrics.toml"

# json
j = json.loads(JSONF.read_text(encoding="utf-8"))
r18 = next(i for i in j["items"] if i["id"] == "R18")
old = r18["description"]
cnt = old.count("单元格")
r18["description"] = old.replace("单元格", "格位")
print(f"  json R18: 替换『单元格』{cnt} 处")
for k in j["items"]:  # 顺带扫全量
    if k["id"] != "R18" and "单元格" in k["description"]:
        k["description"] = k["description"].replace("单元格", "格位")
        print(f"  json {k['id']}: 同样清理")
JSONF.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

# toml
raw = TOML.read_text(encoding="utf-8")
t = tomllib.loads(raw)
t18 = next(c for c in t["criterion"] if c["id"] == "R18")
if "单元格" in t18["description"]:
    new_desc = t18["description"].replace("单元格", "格位")
    if t18["description"] in raw:
        raw = raw.replace(t18["description"], new_desc, 1)
        print(f"  toml R18: 替换完成")
    else:
        # 退化：全量替换"单元格"
        n = raw.count("单元格")
        raw = raw.replace("单元格", "格位")
        print(f"  toml 全量替换『单元格』{n} 处")
TOML.write_text(raw, encoding="utf-8", newline="\n")

# 校验
t2 = tomllib.loads(TOML.read_text(encoding="utf-8"))
j2 = json.loads(JSONF.read_text(encoding="utf-8"))
jt = {c["id"]: c for c in t2["criterion"]}
jj = {i["id"]: i for i in j2["items"]}
print()
print("  双文件 description 一致:", not [k for k in jt if jt[k]["description"] != jj[k]["description"]])
print("  全局『单元格』残留 json:", sum(i["description"].count("单元格") for i in j2["items"]),
      " toml:", sum(c["description"].count("单元格") for c in t2["criterion"]))
print("  R18 描述尾:", jj["R18"]["description"][-140:])
