#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RL0-1 题包质检：一次跑完所有可机械判定的门禁，并汇总成可回填的质检报告。

用法:
    python qc_check.py <题目目录|批次目录> [--zip <交付zip>] [--out <输出目录>] [--json]

做的事：
  1. 自动识别目标是单题还是整批（递归找含 task.toml 的目录）；
  2. 逐题跑题包门禁、判据门禁、判据风格、复杂度、题面/答案/判据一致性交叉检查；
  3. 整批补跑配额与分布，给了 zip 就补跑 zip 内权限/换行检查；
  4. 输出 qc_machine_report.json + qc_machine_report.md，内含机器结论、逐条原始输出、
     以及“必须人工判断、脚本覆盖不到”的待办清单。

降级口径（本地增量）：脚本查的口径规范尚未下发（如 weakness 正式词表）时，该 FAIL 记 TBD、
不计入阻断，报告里单列“脚本口径与规范冲突”小节。见 SKILL.md 硬规则的两条例外。

脚本只下机器结论；最终「通过 / 有条件通过 / 不通过」由质检人结合人工项判定。
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

PER_TASK_GATES = [
    # (脚本, 判定等级, 说明)
    ("validate_task_package.py", "阻断", "题包字段、权重、分布、skill_set 约束"),
    ("validate_rubrics.py", "阻断", "判据门禁 + json/toml 一致性 + 锚点一致性"),
    ("check_task_qc.py", "阻断", "题面/标准答案/判据 跨文件一致性交叉检查"),
    ("check_complexity.py", "阻断", "C1–C5 档位与文件数/产物数/Requirement/工具种类数是否自洽"),
    ("check_rubric_style.py", "重要", "判据措辞：提问式/模糊量词/领域措辞/锚点待核"),
]

EXTRA_ARGS = {"check_rubric_style.py": ["--strict"]}

FAIL_TOTAL = re.compile(r"FAIL\s*合计[:：]\s*(\d+)")

# 本地增量：脚本查的口径规范还没下发时，把该 ERROR 降级为 TBD，不计入阻断。
# 见 SKILL.md 硬规则「机器门禁 FAIL 一律算阻断」的例外①。只在该脚本的**所有** ERROR
# 行都被 TBD 规则解释掉时才降级——还混着别的 ERROR 就保持阻断。
TBD_RULES = [
    ("validate_task_package.py",
     re.compile(r"weakness_tag 需按算法词表填写"),
     "weakness 正式词表未随规范下发 → TBD，由算法侧提供；拿到词表后一键替换 W 编号。"
     "按描述式填写不等于「照抄占位示例 W07-流程跳步」，不构成阻断", None),
    ("validate_task_package.py",
     re.compile(r"缺少必须覆盖的维度"),
     "维度表按领域核定，目前只有法律/办公类的 11 个固定维度名有依据；"
     "金融、代码、skill 类用什么维度未下发 → TBD，回甲方确认该领域的必覆盖维度。"
     "真实案例：FIN1-skill-DEP-003 无「指令遵循」维度，甲方人检仍判「完整性 ✅ 合格」", "法律"),
]


def task_domain(task_dir):
    """读 task.toml 的 domain（用于判断领域相关口径是否适用）。"""
    path = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(path):
        return ""
    text = open(path, encoding="utf-8").read()
    m = re.search(r'(?m)^domain\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def split_tbd(script, out, task_dir=None):
    """返回 (未被 TBD 解释的 ERROR 行, 归入 TBD 的说明列表)。

    规则的最后一个元素是「仅当 domain 不含该关键词时才降级」，None 表示无条件降级。
    领域含「法律」时，法律领域的口径一律不放宽。
    """
    residual, tbd = [], []
    domain = task_domain(task_dir) if task_dir else ""
    for line in out.splitlines():
        s = line.strip()
        if not s.startswith("ERROR:"):
            continue
        for scr, pat, note, guard in TBD_RULES:
            if scr == script and pat.search(s):
                if guard and guard in domain:
                    break
                tbd.append(f"{s}  →  {note}")
                break
        else:
            residual.append(s)
    return residual, tbd


def find_task_dirs(target):
    """目标是题目目录就返回它；是批次目录就返回下一层里含 task.toml 的目录。"""
    target = os.path.abspath(target).rstrip("\\/")
    if os.path.isfile(os.path.join(target, "task.toml")):
        return [target], [target]
    found = []
    for name in sorted(os.listdir(target)):
        sub = os.path.join(target, name)
        if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "task.toml")):
            found.append(sub)
    return found, [target]


def run(args, timeout=900):
    cmd = [sys.executable] + args
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        out = (proc.stdout or b"").decode("utf-8", "replace")
        err = (proc.stderr or b"").decode("utf-8", "replace")
        return proc.returncode, (out + ("\n" + err if err.strip() else "")).strip()
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(args)}"
    except Exception as exc:  # noqa: BLE001
        return 125, f"ERROR running {' '.join(args)}: {exc}"


def gate_failed(script, rc, out):
    """把各脚本不同的输出约定统一成 是否失败。"""
    if rc == 124 or rc == 125:
        return True
    if script == "check_rubric_style.py":
        m = FAIL_TOTAL.search(out)
        return bool(m and int(m.group(1)) > 0)
    if script == "check_task_qc.py":
        # 本地增量：该脚本只有「阻断」才非零退出，但「重要」级（题面段缺失、泄露判据用词、
        # prompt.md 缺模板锚点、部分数声明不符 Q-T10…）同样是必须整改项。
        # 只看退出码会把它们吞掉，报告里就看不到题面结构问题。
        return rc != 0 or bool(re.search(r"===\s*重要（\d+）", out))
    m = FAIL_TOTAL.search(out)
    if m:
        return int(m.group(1)) > 0
    return rc != 0 or "[FAIL]" in out


def effective_level(script, out, default_level):
    """按脚本输出里的实际严重度定级：只有「重要」问题的门禁不能按「阻断」计。"""
    if script == "check_task_qc.py":
        if re.search(r"===\s*阻断（\d+）", out):
            return "阻断"
        if re.search(r"===\s*重要（\d+）", out):
            return "重要"
    return default_level


MANUAL_CHECKLIST = [
    ("题面", "任务是否真的可解：材料齐、信息够、无需要模型凭空猜测的法规条款/统计数据"),
    ("题面", "题面显式要求与 instructions 中禁止项是否自洽，有没有互相矛盾的约束"),
    ("题面", "是否靠题面歧义刷低分（hack）：换个合理解读就能得低分，而正确解读无据可依"),
    ("题面", "完成标准段是否泄露判据权重、隐藏断言、解题路径"),
    ("题面", "专项数据：题面是否声明了当前 Environment 可用的工具集合 / MCP，且与 task.toml 一致"),
    ("题面", "专项数据：skill_set 里的 skill 是否真的不可省略（缺了它任务必然做不对），还是只是背景文档"),
    ("题面", "weakness 数据：weakness_tag 标注的 trigger 是否真的埋在题面/environment 里，且必然诱发失败"),
    ("标准答案", "参考答案是否专业正确：结论、口径、计算、引用与材料原文一致"),
    ("标准答案", "参考答案是否依赖了题面未提供或环境内不存在的信息"),
    ("标准答案", "参考答案是否会被题面允许的另一种正确做法判为错误（判据过窄）"),
    ("rubrics", "判据锚点是否都能在 environment/input_files/ 找到出处，没有把自造口径写成得分前提"),
    ("rubrics", "判据是否覆盖了题面的全部显式要求（Requirement Coverage），有无漏项"),
    ("rubrics", "判据描述能否被不同 Judge 稳定复现，边界描述是否有二义"),
    ("rubrics", "同一角度是否既写正分又写负分，或同一问题被重复计分"),
    ("题包", "跑分产物与轨迹是否完整：每执行体的 output / reward.json / reward-details.json / 轨迹"),
    ("题包", "难度是否实测达标：参考答案 ≥0.85，三模型均值 <0.7（A1/A2/A3 分档），且至少一个模型非零"),
    ("题包", "派生新批次是否正确继承了上一轮返修成果（判据/答案/模板与上一轮最终态逐文件比对）"),
]


def main():
    ap = argparse.ArgumentParser(description="RL0-1 题包质检（题面 / 标准答案 / rubrics）")
    ap.add_argument("target", help="题目目录或批次目录")
    ap.add_argument("--zip", dest="zip_path", help="交付 zip，用于补跑包内权限/换行检查")
    ap.add_argument("--out", help="报告输出目录（默认 <target>_qc/，不写进题包内）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON 摘要")
    ap.add_argument("--fast", action="store_true",
                    help="跳过判据锚点的材料正文比对（大批量质检提速，之后需补跑）")
    ap.add_argument("--jobs", type=int, default=4, help="并行执行体数量，默认 4")
    args = ap.parse_args()

    target = os.path.abspath(args.target).rstrip("\\/")
    tasks, batch_roots = find_task_dirs(target)
    out_dir = args.out or (target + "_qc")
    os.makedirs(out_dir, exist_ok=True)

    report = {
        "target": target,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tasks": [],
        "batch_checks": [],
        "manual_checklist": [{"scope": a, "item": b} for a, b in MANUAL_CHECKLIST],
    }
    blocking = important = 0

    jobs = [(task_dir, script, level, desc)
            for task_dir in tasks
            for script, level, desc in PER_TASK_GATES]
    results = {}

    def worker(item):
        task_dir, script, level, desc = item
        extra = list(EXTRA_ARGS.get(script, []))
        if args.fast and script == "check_rubric_style.py":
            extra.append("--no-material")
        rc, out = run([os.path.join(HERE, script), task_dir] + extra)
        return item, rc, out

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for item, rc, out in pool.map(worker, jobs):
            results[(item[0], item[1])] = (rc, out)

    for task_dir in tasks:
        entry = {"task": os.path.basename(task_dir), "path": task_dir, "gates": []}
        for script, level, desc in PER_TASK_GATES:
            rc, out = results[(task_dir, script)]
            failed = gate_failed(script, rc, out)
            tbd = []
            gate_level = effective_level(script, out, level)
            if failed:
                residual, tbd = split_tbd(script, out, task_dir)
                if tbd and not residual:
                    # 只有「规范未下发的口径」这一类原因 → 降级为 TBD，不占阻断名额
                    failed = False
                else:
                    tbd = []
            entry["gates"].append({
                "script": script, "desc": desc, "level": gate_level,
                "failed": failed, "tbd": tbd, "exit_code": rc, "output": out,
            })
            if failed:
                if gate_level == "阻断":
                    blocking += 1
                else:
                    important += 1
            elif tbd:
                entry.setdefault("tbd", []).extend(tbd)
        report["tasks"].append(entry)

    # 整批：配额与分布
    if len(tasks) > 1:
        rc, out = run([os.path.join(HERE, "check_batch_quota.py"), target])
        failed = gate_failed("check_batch_quota.py", rc, out)
        report["batch_checks"].append({
            "script": "check_batch_quota.py", "desc": "批次配额、weakness 覆盖、复杂度与难度分布",
            "level": "重要", "failed": failed, "exit_code": rc, "output": out,
        })
        important += int(failed)

    # zip 内权限 / 换行
    if args.zip_path:
        rc, out = run([os.path.join(HERE, "check_package_permissions.py"), os.path.abspath(args.zip_path)])
        failed = gate_failed("check_package_permissions.py", rc, out)
        report["batch_checks"].append({
            "script": "check_package_permissions.py", "desc": "zip 内 solve.sh/test.sh 权限位与换行",
            "level": "阻断", "failed": failed, "exit_code": rc, "output": out,
        })
        blocking += int(failed)

    verdict = "不通过（打回）" if blocking else ("有条件通过（需整改后复检）" if important else "通过")
    report["machine_summary"] = {"blocking": blocking, "important": important,
                                 "machine_verdict": verdict,
                                 "task_count": len(tasks)}

    with open(os.path.join(out_dir, "qc_machine_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    lines = [f"# 质检机器门禁报告", "",
             f"- 质检对象：`{target}`",
             f"- 题目数：{len(tasks)}",
             f"- 生成时间：{report['generated_at']}",
             f"- 机器结论：**{verdict}**（阻断 {blocking} 项 / 重要 {important} 项）", "",
             "> 机器门禁只覆盖可机械判定的部分。最终结论必须结合下方待人工项与质检人的判断；"
             "所有机器 FAIL 一律按阻断处理，只有「规范口径未下发」「脚本映射与规范不一致」"
             "两类按 TBD 单列（见下方 TBD 小节，不计入阻断）。", ""]
    for entry in report["tasks"]:
        lines.append(f"## {entry['task']}")
        lines.append("")
        lines.append("| 门禁 | 等级 | 结果 |")
        lines.append("|---|---|---|")
        for g in entry["gates"]:
            mark = "FAIL" if g["failed"] else ("TBD" if g.get("tbd") else "PASS")
            lines.append(f"| {g['script']}（{g['desc']}） | {g['level']} | "
                         f"{mark} |")
        lines.append("")
        for g in entry["gates"]:
            if g["failed"]:
                lines.append(f"### {entry['task']} · {g['script']} 原始输出")
                lines.append("")
                lines.append("```text")
                lines.append(g["output"])
                lines.append("```")
                lines.append("")
    for g in report["batch_checks"]:
        lines.append(f"## 批次级 · {g['script']}（{'FAIL' if g['failed'] else 'PASS'}）")
        lines.append("")
        lines.append("```text")
        lines.append(g["output"])
        lines.append("```")
        lines.append("")
    tbd_items = [(e["task"], t) for e in report["tasks"] for t in e.get("tbd", [])]
    if tbd_items:
        lines.append("## 脚本口径与规范冲突（TBD，不计入阻断）")
        lines.append("")
        lines.append("> 这些 FAIL 的原因是规范口径未下发或脚本映射与规范定义不一致，"
                     "按 SKILL.md 硬规则的两条例外降级为 TBD；整改动作照写，是否放行由甲方裁决。")
        lines.append("")
        for task, item in tbd_items:
            lines.append(f"- **{task}**：{item}")
        lines.append("")
    lines.append("## 待人工 / AI 判断项（脚本覆盖不到）")
    lines.append("")
    cur = None
    for item in report["manual_checklist"]:
        if item["scope"] != cur:
            cur = item["scope"]
            lines.append(f"**{cur}**")
            lines.append("")
        lines.append(f"- [ ] {item['item']}")
    lines.append("")

    with open(os.path.join(out_dir, "qc_machine_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    if args.json:
        print(json.dumps(report["machine_summary"], ensure_ascii=False, indent=2))
    else:
        print(f"[{verdict}] 题目 {len(tasks)} 个｜阻断 {blocking}｜重要 {important}")
        for entry in report["tasks"]:
            bad = [g["script"] for g in entry["gates"] if g["failed"]]
            tbd = [g["script"] for g in entry["gates"] if g.get("tbd")]
            text = ("FAIL: " + ", ".join(bad)) if bad else "PASS"
            if tbd:
                text += f"（TBD: {', '.join(tbd)}）"
            print(f"  {entry['task']:<16} {text}")
        for g in report["batch_checks"]:
            print(f"  [批次] {g['script']:<28} {'FAIL' if g['failed'] else 'PASS'}")
        print(f"\n报告目录：{out_dir}")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
