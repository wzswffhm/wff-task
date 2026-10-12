# -*- coding: utf-8 -*-
"""序号 239 第五轮返修：修订退出回报口径与 R27。

只修改任务题包与证据副本，不修改任何输入材料。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-weakness" / "FIN3-WKN-150"
EVIDENCE = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第五轮返修"
            / "evidence" / "fix6_extract" / "work_fin-b01_20261006_fix6-150" / "FIN3-WKN-150")
BACKUP = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第五轮返修"
          / "evidence" / "before_fix7")
APPLY = "--apply" in sys.argv

OLD_R27 = (
    "退出回报测算正确：给出明确的退出假设（如按 2029 年上市、以可比公司 PE 中位数与 2027 年承诺净利润"
    "计算上市后市值约 290,000 万元），据此测算持股比例中值（约 6.6%）对应的退出价值约 19,000 万元"
    "（允许 ±10%），投资回报倍数约 1.27 倍（允许 ±0.15 倍），三年年化回报约 8%—9%（允许 ±3 个百分点），"
    "并指出回报空间有限。 Deliverables to inspect: `/app/output/FIN3-WKN-150_PreIPO投资决策备忘录.md`."
)
NEW_R27 = (
    "退出回报口径披露正确：明确指出输入材料未给出可直接采用的退出时点、退出日估值口径、锁定减持期和退出日"
    "持股比例，故可靠的绝对退出价值、MOIC/IRR 及固定年化回报均无法由材料直接确认并标注“待核实”；同时说明"
    "33号材料仅约定 2029-12-31 前完成上市申报，不等于完成上市或投资退出，32号材料又禁止引入参数以外假设。"
    "在此基础上，如给出任何退出数值，必须同时标注为条件分析并列明其假设来源；若采用演示性条件情景（建议以"
    "可比公司 PE 中位数 16.12 倍与 2027 年承诺扣非归母净利润 18,000 万元计算上市后市值约 290,000 万元，"
    "持股比例约 6.6% 对应退出价值约 19,000 万元、回报倍数约 1.27 倍、三年年化约 8%—9%），数值须落入上述"
    "容差并明确该情景不构成材料已确认事实。Deliverables to inspect: "
    "`/app/output/FIN3-WKN-150_PreIPO投资决策备忘录.md`."
)

EXIT_REPLACEMENTS = [
    (
        "- **退出回报测算**：假设 2029 年上市、按可比公司 PE 中位数 16.12 倍与 2027 年承诺利润 18,000 万元"
        "计算，上市后市值约 290,160 万元；按中值持股比例 6.50% 测算，退出价值约 18,873 万元，相对投资本金 "
        "15,000 万元约 **1.26 倍**（三年年化约 8.0%）。**回报空间有限，估值安全垫偏薄。**",
        "- **退出回报测算与信息边界**：输入材料未给出可直接采用的退出时点、退出日估值口径、锁定减持期及退出日"
        "持股比例；33号材料仅约定 2029-12-31 前完成上市申报，并不等于完成 IPO 或投资退出，32号材料又明确"
        "“参数以外的假设不得自行引入”。因此，可靠的绝对退出价值、MOIC/IRR 及固定年化回报**待核实**，不得将"
        "下述条件测算表述为材料已确认事实。为满足情景分析要求，以下数值仅作**条件分析**：若以可比公司 PE 中位数 "
        "16.12 倍与 2027 年承诺扣非归母净利润 18,000 万元测算上市后市值约 290,160 万元，按中值持股比例 6.50% "
        "对应退出价值约 18,873 万元、相对投资本金 15,000 万元约 1.26 倍（三年年化约 8.0%）；该情景的回报空间"
        "有限、估值安全垫偏薄，实际退出结果仍待补齐退出日参数后核实。",
    ),
    (
        "- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年承诺利润"
        "测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。",
        "- **退出安排**：33号材料仅将 2029-12-31 前完成上市申报设为回购触发条件，不能据此认定 2029 年完成"
        "上市或投资退出；退出回报须在取得退出日参数后复核，现阶段标注“待核实”。若未按期完成上市申报或承诺"
        "未达标，依据回购条款由控股股东按投资本金加年化 8% 单利回购本次投资本金。",
    ),
]


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    files = {
        "memo_golden": TASK / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        "memo_tests": TASK / "tests" / "__golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        "script_golden": TASK / "solution" / "golden_output" / "FIN3-WKN-150_reproduce.py",
        "script_tests": TASK / "tests" / "__golden_output" / "FIN3-WKN-150_reproduce.py",
        "rubric_toml": TASK / "tests" / "rubrics.toml",
        "rubric_json": TASK / "rubrics.json",
        "task_toml": TASK / "task.toml",
    }
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(missing))

    changes = {}
    for label in ("memo_golden", "memo_tests", "script_golden", "script_tests",
                  "rubric_toml", "rubric_json", "task_toml"):
        changes[label] = read(files[label])

    for label in ("memo_golden", "memo_tests"):
        for index, (old, new) in enumerate(EXIT_REPLACEMENTS, 1):
            changes[label] = replace_once(changes[label], old, new, f"{label} exit block {index}")

    # Script strings are emitted literally in generated Markdown.
    script_old_1 = (
        "A(f'- **退出回报测算**：假设 2029 年上市、按可比公司 PE 中位数 {med_pe:.2f} 倍与 2027 年承诺利润'\n"
        "  f' {fm(promise[\"2027\"])} 万元计算，上市后市值约 {fm(mcap_ipo)} 万元；按中值持股比例'\n"
        "  f' {stake_mid * 100:.2f}% 测算，退出价值约 {fm(exit_val)} 万元，相对投资本金 {fm(invest)} 万元'\n"
        "  f'约 **{multiple:.2f} 倍**（三年年化约 {irr * 100:.1f}%）。**回报空间有限，估值安全垫偏薄。**')"
    )
    script_new_1 = (
        "A('- **退出回报测算与信息边界**：输入材料未给出可直接采用的退出时点、退出日估值口径、锁定减持期及'\n"
        "  '退出日持股比例；33号材料仅约定 2029-12-31 前完成上市申报，并不等于完成 IPO 或投资退出，'\n"
        "  '32号材料又明确“参数以外的假设不得自行引入”。因此，可靠的绝对退出价值、MOIC/IRR 及固定年化'\n"
        "  '回报**待核实**，不得将下述条件测算表述为材料已确认事实。为满足情景分析要求，以下数值仅作'\n"
        "  '**条件分析**：若以可比公司 PE 中位数 {med_pe:.2f} 倍与 2027 年承诺扣非归母净利润 '\n"
        "  '{fm(promise[\"2027\"])} 万元测算上市后市值约 {fm(mcap_ipo)} 万元，按中值持股比例 '\n"
        "  '{stake_mid * 100:.2f}% 对应退出价值约 {fm(exit_val)} 万元、相对投资本金 {fm(invest)} 万元约 '\n"
        "  '**{multiple:.2f} 倍**（三年年化约 {irr * 100:.1f}%）；该情景的回报空间有限、估值安全垫偏薄，'\n"
        "  '实际退出结果仍待补齐退出日参数后核实。')"
    )
    script_old_2 = (
        "A('- **退出安排**：以标的公司 2029 年上市为主要退出路径，退出回报按可比公司 PE 中位数与 2027 年'\n"
        "  '承诺利润测算；若未按期上市或承诺未达标，依据回购条款由控股股东按约定利率回购本次投资本金。')"
    )
    script_new_2 = (
        "A('- **退出安排**：33号材料仅将 2029-12-31 前完成上市申报设为回购触发条件，不能据此认定 2029 年'\n"
        "  '完成上市或投资退出；退出回报须在取得退出日参数后复核，现阶段标注“待核实”。若未按期完成'\n"
        "  '上市申报或承诺未达标，依据回购条款由控股股东按投资本金加年化 8% 单利回购本次投资本金。')"
    )
    changes["script_golden"] = replace_once(changes["script_golden"], script_old_1, script_new_1, "script golden exit return")
    changes["script_golden"] = replace_once(changes["script_golden"], script_old_2, script_new_2, "script golden exit arrangement")
    changes["script_tests"] = changes["script_golden"]

    for label in ("rubric_toml", "rubric_json"):
        changes[label] = replace_once(changes[label], OLD_R27, NEW_R27, f"{label} R27")
    changes["task_toml"] = replace_once(changes["task_toml"], 'version = "1.0.6"', 'version = "1.0.7"', "task version")

    print("=== Planned changes ===")
    for label, path in files.items():
        print(f"  {label:14} {path}")
    print(f"  R27 chars: {len(OLD_R27)} -> {len(NEW_R27)}")
    print(f"  new golden memo sha: {hashlib.sha256(changes['memo_golden'].encode()).hexdigest()[:16]}")
    print(f"  new script sha: {hashlib.sha256(changes['script_golden'].encode()).hexdigest()[:16]}")
    print(f"  identical memo copies: {changes['memo_golden'] == changes['memo_tests']}")
    print(f"  identical script copies: {changes['script_golden'] == changes['script_tests']}")
    if not APPLY:
        print("DRY RUN: no files written")
        return 0

    if BACKUP.exists():
        shutil.rmtree(BACKUP)
    BACKUP.mkdir(parents=True)
    for label, path in files.items():
        target = BACKUP / path.name
        if target.exists():
            target = BACKUP / f"{label}__{path.name}"
        shutil.copy2(path, target)
    print(f"backup: {BACKUP}")

    for label, path in files.items():
        write(path, changes[label])
        print(f"wrote: {path}  sha256={sha(path)[:16]}")

    assert read(files["memo_golden"]) == read(files["memo_tests"])
    assert read(files["script_golden"]) == read(files["script_tests"])
    print("APPLY complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
