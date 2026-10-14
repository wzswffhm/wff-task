# -*- coding: utf-8 -*-
"""check_windows_mechanism.py 的自测（正例 + 9 个反例）。

用真实合规题 019 的最小文件集做夹具，逐个变体验证门禁判定方向正确。
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile

SKILL = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\skills\harbor-windows\scripts"
SRC019 = r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-14_Windows-48题质检-专家修复详解版\extracted\019"

spec = importlib.util.spec_from_file_location("cwm", os.path.join(SKILL, "check_windows_mechanism.py"))
cwm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cwm)

KEEP = ["task.toml", "instruction.md", "metadata/windows_mechanism.json",
        "tests/required_testcases.json", "tests/Verifier.cs"]


def make_fixture(tmp):
    dst = os.path.join(tmp, "task")
    for rel in KEEP:
        s = os.path.join(SRC019, rel.replace("/", os.sep))
        d = os.path.join(dst, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(s, d)
    return dst


def edit_gate(task, fn):
    p = os.path.join(task, "metadata", "windows_mechanism.json")
    with io.open(p, encoding="utf-8") as f:
        g = json.load(f)
    fn(g)
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(g, f, ensure_ascii=False, indent=2)


cases = []


def case(name, mutate=None, inject=None, drop_gate=False, exempt=False, allow_exempt=False, expect_pass=None):
    cases.append(dict(name=name, mutate=mutate, inject=inject, drop_gate=drop_gate,
                      exempt=exempt, allow_exempt=allow_exempt, expect_pass=expect_pass))


case("正例：019 原样", expect_pass=True)
case("反例1：counterfactual.answer=是", mutate=lambda g: g["counterfactual"].update(answer="是"), expect_pass=False)
case("反例2：mechanisms 仅 2 条", mutate=lambda g: g.update(mechanisms=g["mechanisms"][:2]), expect_pass=False)
case("反例3：f2p_case 指向 P2P 用例", mutate=lambda g: g["mechanisms"][0].update(f2p_case="basic_binary"), expect_pass=False)
case("反例4：test_ref 指向不存在文件", mutate=lambda g: g["mechanisms"][0].update(test_ref="tests/nope.ps1#L1"), expect_pass=False)
case("反例5：instruction_quote 不在题面", mutate=lambda g: g["mechanisms"][0].update(instruction_quote="这是一句题面里根本不存在的话。"), expect_pass=False)
case("反例6：排他声明不匹配", mutate=lambda g: g["exclusive_declaration"].update(quote="仅 Linux 语义，无需 Windows 支持。"), expect_pass=False)
case("反例7：non_windows_must_fail 证据不匹配", mutate=lambda g: g["non_windows_must_fail"].update(evidence="if (not windows) throw"), expect_pass=False)
case("反例8：题面注入自认句", inject="本题不主张 Windows 反事实价值，按通用编码能力归类。", expect_pass=False)
case("反例9：缺门禁产物且无豁免", drop_gate=True, expect_pass=False)
case("反例10：有豁免但未开开关", drop_gate=True, exempt=True, allow_exempt=False, expect_pass=False)
case("正例11：有豁免且开开关（F6 仍生效）", drop_gate=True, exempt=True, allow_exempt=True, expect_pass=True)

ok = True
with tempfile.TemporaryDirectory() as tmp:
    for i, c in enumerate(cases):
        work = os.path.join(tmp, "case%02d" % i)
        os.makedirs(work, exist_ok=True)
        task = make_fixture(work)
        if c["mutate"]:
            edit_gate(task, c["mutate"])
        if c["inject"]:
            p = os.path.join(task, "instruction.md")
            with io.open(p, "a", encoding="utf-8") as f:
                f.write("\n\n" + c["inject"] + "\n")
        if c["drop_gate"]:
            os.remove(os.path.join(task, "metadata", "windows_mechanism.json"))
        if c["exempt"]:
            with io.open(os.path.join(task, "WINDOWS_MECHANISM_EXEMPT.md"), "w", encoding="utf-8") as f:
                f.write("该包按通用编码题池交付，不申报 Windows 专属能力。\n")
        res, _ = cwm.check_task(task, None, c["allow_exempt"])
        got = res.valid
        flag = "OK " if got == c["expect_pass"] else "BAD"
        if got != c["expect_pass"]:
            ok = False
        print("%s  %-34s expect=PASS?%-5s got=PASS?%-5s errors=%d flags=%d"
              % (flag, c["name"], c["expect_pass"], got, len(res.errors), len(res.warnings)))
        if got != c["expect_pass"]:
            for e in res.errors:
                print("        - %s" % e)

print()
print("自测结果:", "全部通过" if ok else "存在不符合预期的用例")
sys.exit(0 if ok else 1)
