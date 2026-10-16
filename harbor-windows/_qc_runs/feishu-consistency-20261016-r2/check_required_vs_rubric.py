"""校验 tests/required_testcases.json 与 rubric.json / judge.toml 的用例集合与分组是否一致。"""
import json
import os
import re

HW = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"

for pkg in sorted(p for p in os.listdir(HW) if p.startswith("wfflab__")):
    tests = os.path.join(HW, pkg, "tests")
    req_p = os.path.join(tests, "required_testcases.json")
    rub_p = os.path.join(tests, "rubric.json")
    req = json.load(open(req_p, encoding="utf-8")) if os.path.exists(req_p) else []
    rub = json.load(open(rub_p, encoding="utf-8")) if os.path.exists(rub_p) else {}
    rub_ids = [i for it in rub.get("items", []) for i in it.get("test_ids", [])]

    req_ids = [r["id"] for r in req]
    req_group = {r["id"]: str(r.get("group", "")).upper() for r in req}
    prefix_mismatch = [i for i in req_ids
                       if (i.startswith("f2p-") and req_group[i] != "F2P")
                       or (i.startswith("p2p-") and req_group[i] != "P2P")]
    only_req = sorted(set(req_ids) - set(rub_ids))
    only_rub = sorted(set(rub_ids) - set(req_ids))
    f2p_req = sum(1 for i in req_ids if req_group.get(i) == "F2P")
    p2p_req = sum(1 for i in req_ids if req_group.get(i) == "P2P")
    f2p_rub = sum(1 for i in rub_ids if i.startswith("f2p-"))
    p2p_rub = sum(1 for i in rub_ids if i.startswith("p2p-"))

    print("==== %s" % pkg)
    print("   required: %d 条 (F2P %d / P2P %d) | rubric: %d 条 (F2P %d / P2P %d)" % (
        len(req_ids), f2p_req, p2p_req, len(rub_ids), f2p_rub, p2p_rub))
    if prefix_mismatch:
        print("   [分组与 id 前缀不符] %s" % prefix_mismatch)
    if only_req:
        print("   [仅 required 有] %s" % only_req)
    if only_rub:
        print("   [仅 rubric 有] %s" % only_rub)
    if not (prefix_mismatch or only_req or only_rub):
        print("   集合与分组一致")
