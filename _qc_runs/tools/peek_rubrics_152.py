# -*- coding: utf-8 -*-
"""查看 rubrics.json 顶层结构与 metadata（改判据时需同步的部分）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152\rubrics.json")
j = json.loads(p.read_text(encoding="utf-8"))
print("顶层键:", list(j.keys()))
for k, v in j.items():
    if k == "items":
        print(f"  items: list[{len(v)}]")
        print(f"    item[0] 键: {list(v[0].keys())}")
        print(f"    item[0] 示例: {json.dumps(v[0], ensure_ascii=False)[:700]}")
    elif isinstance(v, (dict, list)):
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:900]}")
    else:
        print(f"  {k}: {v}")

# toml 顶层
import tomllib
t = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152\tests\rubrics.toml")
tt = tomllib.loads(t.read_text(encoding="utf-8"))
print()
print("toml 顶层键:", list(tt.keys()))
for k, v in tt.items():
    if k == "criterion":
        print(f"  criterion: list[{len(v)}]")
        print(f"    [0] 键: {list(v[0].keys())}")
    else:
        print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:600]}")
