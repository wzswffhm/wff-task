#!/usr/bin/env python3
"""判据锚点溯源检查：判据不得要求题面没有的东西。

对每题抽取每条 criterion 里的「硬锚点」——量化要求（不少于 N 项/条/行/字/句）、
内部编号（RA-/CP-/CO-/RB-/RM-/DJ- …）、表头列名/被引号包裹的短词、交付物文件名——
再回查 `instruction.md` 与题面明确要求遵守的 `environment/skills/*/SKILL.md`。
两者都找不到的锚点会被列为「疑似题面未覆盖」，供人工确认。

用法:
    python check_rubric_grounding.py <task-dir> [<task-dir> ...] [--json]

退出码: 0 = 没有疑似项；1 = 存在疑似项（需人工确认或删条）。

注意：这是**候选清单**，不是最终判决。像"第 33 条"这类法条序号本来就应由模型从
参考文件里检索得到，题面只需写明"须引用条文序号"，此类命中属正常，人工确认后忽略即可；
真正要处理的是"判据提出了题面与规范都没提过的交付内容/形式/口径"。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ANCHORS = [
    ("量化要求", re.compile(r"(?:不少于|至少|不低于|不超过|不多于|至多)\s*\d+\s*(?:项|条|行|字|句|个编号)")),
    ("裸数量", re.compile(r"\d+\s*(?:项|条|行|字|句)")),
    ("内部编号", re.compile(r"\b(?:RA|CP|CO|RB|RM|DJ|CL)-?\d{1,2}\b")),
    ("文件名", re.compile(r"\b[\w\u4e00-\u9fff.\-]+\.(?:md|docx|xlsx|pdf|csv)\b")),
    ("列名", re.compile(r"「([^「」]{2,12})」|`([^`]{2,12})`")),
]


def load_items(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("items", "rubrics", "criteria"):
            if isinstance(data.get(key), list):
                return data[key]
    return data if isinstance(data, list) else []


def collect_text(task: Path) -> str:
    parts = []
    instr = task / "instruction.md"
    if instr.is_file():
        parts.append(instr.read_text(encoding="utf-8", errors="replace"))
    skills = task / "environment" / "skills"
    if skills.is_dir():
        for md in skills.rglob("SKILL.md"):
            parts.append(md.read_text(encoding="utf-8", errors="replace"))
    for extra in ("tests/prompt.md",):
        p = task / extra
        if p.is_file():
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def check(task: Path) -> dict:
    rub = task / "rubrics.json"
    if not rub.is_file():
        rub = task / "tests" / "rubrics.json"
    items = load_items(rub)
    corpus = collect_text(task)
    flagged = []
    for it in items:
        desc = str(it.get("description") or "")
        missing = []
        for label, pat in ANCHORS:
            for m in pat.findall(desc):
                token = next((g for g in (m if isinstance(m, tuple) else (m,)) if g), "")
                if not token:
                    continue
                if token not in corpus:
                    missing.append(f"{label}:{token}")
        if missing:
            flagged.append({
                "id": it.get("id"),
                "weight": it.get("weight"),
                "description": desc[:120],
                "missing": sorted(set(missing)),
            })
    return {"task": task.name, "items": len(items), "flagged": flagged}


def main() -> int:
    ap = argparse.ArgumentParser(description="判据锚点溯源检查")
    ap.add_argument("task_dirs", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = [check(Path(d).expanduser().resolve()) for d in args.task_dirs]
    total = sum(len(r["flagged"]) for r in results)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if total else 0

    for r in results:
        print(f"[{'WARN' if r['flagged'] else 'PASS'}] {r['task']}  "
              f"疑似题面未覆盖 {len(r['flagged'])} / {r['items']} 条")
        for f in r["flagged"]:
            print(f"  - {f['id']} (w={f['weight']}): {f['description']}")
            print(f"      题面/规范中未找到: {' | '.join(f['missing'][:8])}")
    print("\n以上为候选清单：法条序号一类属正常（题面只要求『须引用条文序号』）；"
          "要处理的是题面与规范都没提过的交付内容/形式/口径。")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
