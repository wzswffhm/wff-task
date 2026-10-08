#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题面 / 标准答案 / 判据 三者的一致性交叉检查（现有门禁未覆盖的部分）。

用法:
    python check_task_qc.py <task-dir> [...] [--json]

覆盖：
  1. 五件套结构是否存在（instruction.md / task.toml / rubrics.json / environment / tests / solution）
  2. 题面段落：任务说明、参考文件、产出要求、硬约束、完成标准 是否各自独立成段
  3. 题面是否泄露判据（rubric 编号、weight、归一化、评分档位等不该出现在 Agent 可见文本里的信息）
  4. 交付物在六处是否一致：instruction.md、task.toml artifacts、
     [[metadata.deliverables]].path、solution/golden_output/、tests/__golden_output/、
     tests/rubrics.toml 的 `Deliverables to inspect:` 清单
  5. skill_set 非空时，题面是否显式要求“必须通过该 skill 完成，不得用其他方式”
  6. tests/prompt.md 是否为 rewardkit 模板（Fairness anchor / Material map / {criteria} 仍在）
  7. JUDGE_ 前缀变量是否被误写进 [environment.env]
  8. 不可见空白（U+00A0 / U+3000）、solve.sh 与 test.sh 的换行与可执行位
  9. 题面「N 个部分、顺序一致」的部分数声明与实际列出的部分是否自洽
     （本地增量：LAW-002 声明四个部分却列出五个标题、其中「第三部分」重复；
      LAW-004 声明四个部分又在「第二部分之后增加一段」，判官与模型对顺序的理解必然分歧，
      生产方靠判据 R12 写「不影响四部分的齐全性与顺序判定」兜底）
 10. 产出要求段里的缩进残句（行首 1–3 个空格的正文行，编辑替换后的残留）

这些只是可机械判定的部分；“题面是否可解、参考答案是否专业正确、判据是否真实”仍须人工判断。
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

SECTIONS = ("任务说明", "参考文件", "产出要求", "硬约束", "完成标准")
REQUIRED_SECTIONS = ("任务说明", "产出要求", "硬约束")
LEAK_WORDS = ("rubrics.json", "rubrics.toml", "rubric", "判据", "weight", "归一化",
              "s_max", "negate", "criterion", "评分档位", "百分制")
LEAK_ID = re.compile(r"\bR\d{2}\b")
FAIRNESS_ANCHORS = ("Fairness", "Material map", "Reference-solution", "{criteria}")
# 本地增量：rewardkit 有几版模板，「Fairness anchor」段在不同版本里用了不同文字
# （代码类题面常见 "The reference is not an answer key / Never award points because
#  the reference satisfies a criterion"）。语义等价即算命中，不要只认 Fairness 字面。
# 真实案例：FIN1-skill-DEP-003 的 prompt.md（甲方人检通过）没有 Fairness 字样，
# 但有 "The reference is not an answer key or a byte-for-byte diff target..."
FAIRNESS_EQUIV = re.compile(
    r"(fairness|not an answer key|never award points|never deduct for|"
    r"不因.{0,14}参考(解|答案)|参考(解|答案).{0,14}(不是|非)答案|"
    r"不因参考解加(分|给分)|不得因参考解给分)", re.IGNORECASE)
FILE_EXT = ("docx|xlsx|xlsm|pptx|ppt|pdf|md|csv|tsv|txt|json|jsonl|html|png|jpg|jpeg|svg|zip|py|sh")
FILENAME_RE = re.compile(
    rf"[0-9A-Za-z\u4e00-\u9fff_\-（）()]{{2,64}}\.(?:{FILE_EXT})\b", re.IGNORECASE)
DELIVERABLE_MARK = "Deliverables to inspect:"
DELIVERABLE_PATH = re.compile(r"`([^`]*)`")
INVISIBLE = ("\u00a0", "\u3000")

CN_DIGIT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
# 「必须包含以下四个部分」这类部分数声明
PART_DECL = re.compile(r"必须包含以下\s*([一二三四五六七八九十两\d]+)\s*个部分")
# 作为标题起头的「**第X部分：」/「**第X部分（」
PART_HEAD = re.compile(r"^\*\*第([一二三四五六七八九十]+)部分\s*[：:（(]", re.MULTILINE)
# 本地增量（2026-10-02）：题面用「1. **争议焦点**：…」这类编号列表枚举部分时，PART_HEAD
#   匹配不到任何标题，旧版会报「以「**第X部分」起头 0 处」——真实误报：LAW-012（资产评估）
#   题面声明「五个部分」并用 1.–5. 逐条列出，数量自洽却被判重要。此处补一条编号列表计数。
PART_NUM_ITEM = re.compile(r"^\s*\d+\s*[.、]\s*\*\*", re.MULTILINE)
# 「第X部分之后增加/插入一段」——在声明的部分之外又插一段
PART_INSERT = re.compile(
    r"第[一二三四五六七八九十]+部分[^。\n]{0,10}(?:之后|后)\s*(?:增加|插入|补充)")
# 产出要求段里行首 1–3 个空格的正文行（编辑替换残留，markdown 里无意义）
INDENT_LEFTOVER = re.compile(r"^[ \t]{1,3}(?![ \t])\S", re.MULTILINE)


def cn2int(token):
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token == "十":
        return 10
    if token.startswith("十"):
        return 10 + CN_DIGIT.get(token[1:], 0)
    if token.endswith("十"):
        return CN_DIGIT.get(token[0], 0) * 10
    if "十" in token:
        head, _, tail = token.partition("十")
        return CN_DIGIT.get(head, 0) * 10 + CN_DIGIT.get(tail, 0)
    return CN_DIGIT.get(token, 0)


def read_text(path, errors="replace"):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors=errors)


def load_toml(path):
    if tomllib is None:
        return None, "tomllib 不可用（需要 Python 3.11+）"
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh), None
    except Exception as exc:  # noqa: BLE001
        return None, f"task.toml 解析失败：{exc}"


def section_body(text, title):
    """取出 '## <title>' 到下一个同级标题之间的正文。"""
    m = re.search(rf"^#{{1,4}}\s*[0-9一二三四五六七八九十]*[\.、]?\s*{re.escape(title)}\s*$",
                  text, re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#{1,4}\s", rest, re.MULTILINE)
    return (rest[:nxt.start()] if nxt else rest).strip()


def basename_of(artifact):
    return artifact.replace("\\", "/").rstrip("/").split("/")[-1]


def golden_files(task_dir, sub):
    root = os.path.join(task_dir, sub)
    if not os.path.isdir(root):
        return None
    out = []
    for name in os.listdir(root):
        full = os.path.join(root, name)
        if os.path.isfile(full):
            out.append(name)
        elif os.path.isdir(full):
            out.extend(f"{name}/{x}" for x in os.listdir(full))
    return sorted(out)


def criterion_deliverables(task_dir, add):
    """逐条核对 tests/rubrics.toml 的交付物清单，返回 (清单并集, 该文件是否可解析)。"""
    path = os.path.join(task_dir, "tests", "rubrics.toml")
    if not os.path.isfile(path):
        add("阻断", "Q-T05", "缺少 tests/rubrics.toml（Harbor 实际读取的判据文件）")
        return None, False
    if tomllib is None:
        return None, False
    try:
        with open(path, "rb") as fh:
            cfg = tomllib.load(fh)
    except Exception as exc:  # noqa: BLE001
        add("阻断", "Q-T05", f"tests/rubrics.toml 解析失败：{exc}")
        return None, False
    criteria = cfg.get("criterion") or cfg.get("criteria") or []
    paths = set()
    for crit in criteria:
        cid = str(crit.get("id") or crit.get("name") or "?")
        desc = str(crit.get("description") or "")
        marks = desc.count(DELIVERABLE_MARK)
        if marks == 0:
            add("重要", "Q-T05", f"{cid} 的 description 没有 `Deliverables to inspect:` 清单")
            continue
        if marks > 1:
            add("阻断", "Q-T05",
                f"{cid} 的 description 出现 {marks} 段 `Deliverables to inspect:`，判官会误判")
        for tail in desc.split(DELIVERABLE_MARK)[1:]:
            tail = tail.split("\n")[0]
            found = [x.strip() for x in DELIVERABLE_PATH.findall(tail)]
            found = [x for x in found]
            if not found or any(not x for x in found):
                add("阻断", "Q-T05", f"{cid} 的交付物清单为空或含空路径，判官找不到交付物")
            for item in found:
                if item:
                    paths.add(basename_of(item))
    return paths, True


def check_one(task_dir, results):
    task_dir = task_dir.rstrip("\\/")
    name = os.path.basename(task_dir) or task_dir

    def add(level, code, msg, evidence=""):
        results.append({"task": name, "level": level, "code": code,
                        "message": msg, "evidence": evidence})

    # 1. 结构
    for rel in ("instruction.md", "task.toml", "rubrics.json"):
        if not os.path.isfile(os.path.join(task_dir, rel)):
            add("阻断", "Q-T01", f"缺少 {rel}")
    for rel in ("environment", "tests", "solution"):
        if not os.path.isdir(os.path.join(task_dir, rel)):
            add("阻断", "Q-T01", f"缺少 {rel}/ 目录")

    instruction = read_text(os.path.join(task_dir, "instruction.md"))
    if instruction is None:
        return

    # 2. 题面段落
    found = {s: section_body(instruction, s) for s in SECTIONS}
    cn_hits = [s for s in SECTIONS if found[s]]
    if not cn_hits:
        # 本地增量：代码类/英文题面用 Input-Output 式结构，不用中文五段式标题。
        # 一个中文段标题都没有时按「提示」报（该领域模板是否允许由人工/甲方定），
        # 不能按「重要」一刀切（真实案例：FIN1-skill-DEP-003，人检通过）。
        add("提示", "Q-T02",
            "题面未使用中文五段式结构（任务说明/参考文件/产出要求/硬约束/完成标准）；"
            "代码类/英文题面常用 Input–Output 式结构，确认该领域模板是否允许")
    else:
        for s in REQUIRED_SECTIONS:
            if found[s] is None or not found[s].strip():
                add("重要", "Q-T02", f"题面缺少“{s}”段落（或该段为空）")
    if found["硬约束"] is not None:
        body = found["硬约束"]
        if body.startswith("（") and body.rstrip().endswith("）"):
            add("重要", "Q-T02", "硬约束整段被括号包裹，规范要求独立成段、不藏进括号")
        if len(body) < 20:
            add("提示", "Q-T02", "硬约束段落过短，确认禁止项/命名要求是否写全")

    # 3. 题面泄露判据
    for word in LEAK_WORDS:
        if word.lower() in instruction.lower():
            add("重要", "Q-T03", f"题面出现判据用词「{word}」，疑似把评分口径写进 Agent 可见文本")
    m = LEAK_ID.search(instruction)
    if m:
        add("重要", "Q-T03", f"题面出现判据编号 {m.group(0)}")

    # 4. 交付物一致性
    cfg, err = load_toml(os.path.join(task_dir, "task.toml"))
    if err:
        add("阻断", "Q-T04", err)
        cfg = None
    cfg = cfg or {}
    artifacts = [basename_of(a) for a in cfg.get("artifacts", [])
                 if not str(a).rstrip("/").endswith("/artifacts/output")]
    deliverables = [os.path.basename(str(d.get("path", "")))
                    for d in (cfg.get("metadata", {}).get("deliverables") or [])]
    golden = golden_files(task_dir, os.path.join("solution", "golden_output"))
    golden_tests = golden_files(task_dir, os.path.join("tests", "__golden_output"))
    inspected, toml_ok = criterion_deliverables(task_dir, add)

    ref = set(artifacts) | set(deliverables)
    if ref:
        for fname in sorted(ref):
            if fname not in instruction:
                add("阻断", "Q-T04",
                    f"交付物 {fname} 在 task.toml 中声明，但题面 instruction.md 未出现",
                    "题面必须逐条写明文件名、格式、数量")
    if golden is None:
        add("阻断", "Q-T04", "缺少 solution/golden_output/（参考答案载体）")
    elif ref:
        for fname in sorted(ref - set(golden)):
            add("阻断", "Q-T04", f"solution/golden_output/ 缺少交付物 {fname}")
        for fname in sorted(set(golden) - ref):
            add("提示", "Q-T04", f"solution/golden_output/ 多出未在题面声明的文件 {fname}")
    if golden is not None and golden_tests is not None and golden != golden_tests:
        add("阻断", "Q-T04",
            "tests/__golden_output/ 与 solution/golden_output/ 内容不一致",
            f"tests={golden_tests} / solution={golden}")
    if inspected and ref:
        for fname in sorted(ref - inspected):
            add("重要", "Q-T05", f"判据的交付物清单里没有 {fname}")

    # 4b. 题面部分数声明与实际部分标题是否自洽（本地增量）
    decl = PART_DECL.search(instruction)
    heads = PART_HEAD.findall(instruction)
    if decl:
        n_decl = cn2int(decl.group(1))
        head_label = "「**第X部分」"
        if not heads:
            # 题面改用编号列表（1. **…**）枚举，则按产出要求段内的编号条目计数
            scope = found.get("产出要求") or instruction
            heads = PART_NUM_ITEM.findall(scope)
            head_label = "编号列表"
        if n_decl and len(heads) != n_decl:
            add("重要", "Q-T10",
                f"题面声明“包含以下 {n_decl} 个部分”，实际以{head_label}枚举 {len(heads)} 处；"
                f"判官按声明数核对结构、模型按实际条目作答，两边对不上就丢分",
                decl.group(0))
        if head_label != "编号列表":
            dup = sorted({h for h in heads if heads.count(h) > 1})
            if dup:
                add("重要", "Q-T10",
                    "题面同一部分编号重复作为标题出现："
                    + "、".join(f"第{d}部分" for d in dup)
                    + "（多为返修插入段落时未清理原标题）")
    ins = PART_INSERT.search(instruction)
    if ins and decl:
        add("重要", "Q-T10",
            "题面在声明的部分数之外又要求增插一段，与「N 个部分、顺序一致」冲突；"
            "判断顺序时判官与模型必然分歧（生产方常用判据写「不影响…判定」兜底，根因仍在题面）",
            ins.group(0))

    # 4c. 产出要求段里的缩进残句（编辑替换残留）
    body = found.get("产出要求") or ""
    leftover = [ln.strip()[:48] for ln in body.splitlines() if INDENT_LEFTOVER.match(ln)]
    if leftover:
        add("提示", "Q-T11",
            f"产出要求段存在行首缩进的正文行 {len(leftover)} 处（疑似编辑残留），"
            f"如：{leftover[0]}")

    # 5. skill 声明
    skill_set = cfg.get("metadata", {}).get("skill_set", []) or []
    if skill_set:
        low = instruction.lower()
        if "skill" not in low:
            add("阻断", "Q-T06", f"题面未提及 skill（skill_set={skill_set}）")
        else:
            for s in skill_set:
                if str(s).lower() in low:
                    tail = instruction[low.index(str(s).lower()):][:300]
                    if not re.search(r"必须|只能|不得|never|must|only", tail, re.IGNORECASE):
                        add("重要", "Q-T06",
                            f"题面提到 skill `{s}` 但附近没有“必须通过该 skill 完成 / 不得用其他方式”的硬约束")
                    break

    # 6. prompt.md 模板锚点
    prompt = read_text(os.path.join(task_dir, "tests", "prompt.md"))
    if prompt is None:
        add("阻断", "Q-T07", "缺少 tests/prompt.md")
    else:
        for anchor in FAIRNESS_ANCHORS:
            hit = anchor.lower() in prompt.lower()
            if not hit and anchor == "Fairness":
                hit = bool(FAIRNESS_EQUIV.search(prompt))
            if not hit:
                add("重要", "Q-T07",
                    f"tests/prompt.md 缺少模板锚点 `{anchor}`（须用 rewardkit 模板原文）")

    # 7. JUDGE_ 泄漏
    raw_toml = read_text(os.path.join(task_dir, "task.toml")) or ""
    m = re.search(r"^\[environment\.env\]\s*$(.*?)(?=^\[|\Z)", raw_toml, re.MULTILINE | re.DOTALL)
    if m and "JUDGE_" in m.group(1):
        add("阻断", "Q-T08", "JUDGE_ 前缀变量出现在 [environment.env]，只允许写在 [verifier.env]")

    # 8. 不可见空白 / 换行 / 可执行位
    for rel in ("instruction.md", "tests/prompt.md", "tests/rubrics.toml",
                "solution/solve.sh", "tests/test.sh"):
        text = read_text(os.path.join(task_dir, rel))
        if text is None:
            continue
        hits = [f"U+{ord(ch):04X}" for ch in INVISIBLE if ch in text]
        if hits:
            add("重要", "Q-T09", f"{rel} 含不可见空白 {hits}")
        if rel.endswith(".sh"):
            if "\r\n" in text:
                add("阻断", "Q-T09", f"{rel} 含 CRLF 行尾，必须为 LF")
            path = os.path.join(task_dir, rel)
            if os.name == "posix" and not os.access(path, os.X_OK):
                add("阻断", "Q-T09", f"{rel} 无可执行位（须 0755）")


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    dirs = [a for a in args if not a.startswith("-")]
    if not dirs:
        raise SystemExit(__doc__)
    results = []
    for task_dir in dirs:
        check_one(task_dir, results)
    blocking = sum(1 for r in results if r["level"] == "阻断")
    important = sum(1 for r in results if r["level"] == "重要")
    if as_json:
        print(json.dumps({"results": results, "blocking": blocking,
                          "important": important}, ensure_ascii=False, indent=2))
        return 1 if blocking else 0
    for level in ("阻断", "重要", "提示"):
        hits = [r for r in results if r["level"] == level]
        if not hits:
            continue
        print(f"\n=== {level}（{len(hits)}）===")
        for r in hits:
            print(f"  [{r['task']}] {r['code']} {r['message']}")
            if r["evidence"]:
                print(f"        证据：{r['evidence']}")
    print(f"\n合计：阻断 {blocking} 条，重要 {important} 条，共 {len(results)} 条")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
