#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""self_denial_scan.py — 「自我否认 / 通用化 Windows 价值」表述扫描（共享实现）

## 为什么单独抽出来

同一套判据被两个入口使用，必须**逐字一致**，否则会出现"门禁绿、打包红"的自相矛盾：

1. `check_windows_mechanism.py` 的 **F6**（题包门禁，命中 → FAIL，永不豁免）；
2. `package_task_zip.py` 的**出包前扫描**（命中 → 拒绝出包，非零退出）。

冲突时以随包甲方脚本 `_reference/windows-harbor-qc/scripts/` 的行为为准
（`run_qc.py: static_check` / `inspect_delivery.py: inspect_delivery`）；本模块只覆盖其中
甲方未显式实现的一条：**包内不得出现自我否认 Windows 价值的表述**。

## 判据（全部可复算）

1. **容忍夹字（P0-5 修正）**：`通用编码` 与 `能力|题池|题` 之间允许 ≤8 个任意字符。
   实测漏判：`已按同一口径**明确归入通用编码能力**，不主张` —— 关键词被 Markdown 粗体
   与语气副词隔开，旧模式 `通用编码(能力|题池|题)` 直接漏过。
2. **邻近匹配**：`不主张` 与同处其后的 `Windows`（≤40 字符）也算自我否认，
   不要求两个关键词紧邻。
3. 每条命中都锚在**首个关键词**（`anchor` 捕获组）上，再做两类**上下文防误报**判定
   （纯子串判据，不做语义推断；被抑制的条目仍可 `include_suppressed=True` 取出核对）：
   - **否定前缀**：跳过 `*`/空格/引号等 Markdown 装饰后，关键词紧前面就是
     `不归入` / `不主张` / `并非` / `不是` … ⇒ 这是在**反驳归类**，不是自认；
   - **引用来源**：关键词之前出现 `对应…要求` / `来源` / `原文` / `手册` / `引用` /
     `否则归入` … ⇒ 这是在**转述甲方条款**，不是自认。

> 防误报判据来自 `wfflab__wpeimg-219-v1.4.0` 的实测：同一份 `verifier/WINDOWS_VALUE.md`
> 里既有**转述甲方条款**的「否则归入通用编码题池」（标题区引用，不该算自认），
> 也有真正把**别的题**自认句搬进来的 §4（该算）。
> 把上下文判据写死在这里，是为了避免"把引文当自认"。

## 内嵌回归用例（交付前必须仍能命中）

| 用例 | 文本 | 期望 |
|---|---|---|
| HIT-1 | `本题不主张 Windows 反事实价值，按通用编码能力归类。` | 命中 |
| HIT-2 | `已按同一口径**明确归入通用编码能力**，不主张 Windows 反事实价值。` | 命中（P0-5 夹字漏判的实测形态） |
| HIT-3 | `This is a platform-agnostic task.` | 命中 |
| SUPP-1 | `对应甲方要求：**第 3 条「Windows 价值必须真实映射，否则归入通用编码题池」**；` | 抑制（转述甲方条款） |

> 说明：`已按同一口径**明确归入通用编码能力**，不主张` 这一句在**本仓库现行 5 个生效包**里
> 只存在于 `wfflab__wpeimg-219-v1.4.0`（本模块的 HIT-2 实测用例即取自它）。
> `wfflab__wvas-216-v1.0.0` 的 `verifier/WINDOWS_VALUE.md` 在 2026-10-14 批次里已改写为
> 「本题具备真实的 Windows 反事实价值，主张 Windows 采购分类」，**不含**该句；
> 因此修复后 216 仍为 PASS。判断依据以当前包内容为准，不以审计备忘里的转述为准。

## 用法

    from self_denial_scan import scan_self_denial, SELF_DENIAL_PATTERNS

    hits = scan_self_denial(task_dir)                       # 按包扫描
    hits = scan_self_denial(inbox_dir, extra_skip_dirs=("environment/evidence",))

每条 hit 为 dict：`{file, line, text, why, suppressed, suppress_reason}`。
`package_task_zip.py` 只对 `suppressed=False` 的条目拒发。
"""

from __future__ import annotations

import os
import re

# ---------------------------------------------------------------- 判据表

# 每条 = (正则, 说明, kind)
#   kind   : denial 直接自我否认 / classify 自我归类为通用题池 / downgrade 降格为执行平台
#   正则必须含名为 `anchor` 的捕获组：该组起点即"首个关键词"位置，
#   后续的否定前缀 / 引用来源判定都锚在它前面。
SELF_DENIAL_PATTERNS = [
    # ---- 直接自我否认
    (re.compile(r"(?P<anchor>不主张)[^\n]{0,40}Windows"), "自我否认：『不主张 Windows…』", "denial"),
    (re.compile(r"(?P<anchor>不(?:依赖|涉及|要求))[^\n]{0,8}Windows[^\n]{0,8}(?:专属|特有|机制)"),
     "自我否认：不依赖 Windows 专属机制", "denial"),
    (re.compile(r"(?P<anchor>(?:no|not|never)\s+(?:claim|claiming|rely on|relying on|depend on|depending on))"
                r"\s+Windows", re.I), "自我否认：no/not … Windows", "denial"),
    (re.compile(r"(?P<anchor>Windows)\s+(?:relevance|value)[^\n]{0,12}(?:low|none|absent)", re.I),
     "自我否认：Windows relevance low/none", "denial"),
    (re.compile(r"(?P<anchor>not)\s+a\s+Windows[\s-]specific", re.I), "自我否认：not a Windows-specific", "denial"),
    # ---- 自我归类为通用题池（P0-5：容忍关键词之间夹字，≤8 字符）
    (re.compile(r"(?P<anchor>通用编码)[^\n]{0,8}(?:能力|题池|题)"), "自我归类：『通用编码能力/题池』", "classify"),
    (re.compile(r"(?P<anchor>platform[\s-]?agnostic)", re.I), "自我归类：platform-agnostic", "classify"),
    (re.compile(r"(?P<anchor>cross[\s-]?platform)\s+(?:task|problem|implementation)", re.I),
     "自我归类：cross-platform task", "classify"),
    (re.compile(r"(?P<anchor>按通用)[^\n]{0,8}(?:归类|交付|计分)"), "自我归类：按通用…归类", "classify"),
    # ---- 自我降格
    (re.compile(r"(?P<anchor>windows_target)[^\n]{0,40}(?:执行平台|不作为)"),
     "自我降格：windows_target 仅为执行平台", "downgrade"),
]

SCAN_SUFFIXES = {".md", ".toml", ".json", ".ps1", ".bat", ".txt"}

# 默认不扫的子树：测评工作区（含被测样本自述）、历史跑分记录、缓存
SCAN_SKIP_DIRS = ("environment/workspace", "jobs", ".git", "__pycache__", "node_modules")

# 豁免标记是包内元数据声明（其措辞必然含"通用编码"字样），不参与扫描；
# 但它**不得随交付 ZIP 外发**，故豁免生效时由调用方追加 FLAG 提醒。
EXEMPT_FILE = "WINDOWS_MECHANISM_EXEMPT.md"
SCAN_SKIP_FILES = (EXEMPT_FILE,)

# ---- 防误报用的上下文子串（纯字符判据，不做语义推断）

# 关键词紧前面（跳过装饰字符后）是否为否定式归类
_NEGATION_PREFIX = re.compile(r"(?:不归入|不主张|不属于|不列为|不计入|不能归入|并非|不是|非|无|未)$")
# 单个否定字：允许被 ** ` 空白 等装饰字符与关键词隔开（`**不归入**通用编码`）
_NEGATION_CHARS = frozenset("不非无未")
# 允许跨过的"装饰字符"：Markdown 粗体、空白、引号、括号、冒号、破折号
_SEPARATOR_CHARS = frozenset(" \t*_`\"'“”‘’「」『』()（）[]【】:：—–-")
# 遇到这些左侧定界符就停止跨行取前缀：引文内的"归入"不是本句的主张
_LEFT_DELIMITERS = frozenset("「『“‘([【（")
# 引用来源：关键词之前出现这些词，说明是在"转述甲方条款 / 复述质检要求"，不是自认
_CITATION_CONTEXT = re.compile(
    r"(对应[^\n。；;]{0,24}要求|甲方要求|乙方要求|来源|原文|原话|手册|出处|引用"
    r"|质检条目|质检要求|质检意见|专家步骤|修复步骤|规范第|第\s*\d+\s*条"
    r"|否则归入|采购分类|题池归类)")

CITATION_LOOKBACK = 48
# 允许跨过的"装饰字符"：Markdown 粗体、空白、引号、括号、冒号、破折号
_SEPARATOR_CHARS = frozenset(" \t*_`\"'“”‘’「」『』()（）[]【】:：—–-")
# 遇到这些左侧定界符就停止跨行取前缀：引文内的"归入"不是本句的主张
_LEFT_DELIMITERS = frozenset("「『“‘([【（")
# 引用来源：关键词之前出现这些词，说明是在"转述甲方条款 / 复述质检要求"，不是自认
_CITATION_CONTEXT = re.compile(
    r"(对应[^\n。；;]{0,24}要求|甲方要求|乙方要求|来源|原文|原话|手册|出处|引用"
    r"|质检条目|质检要求|质检意见|专家步骤|修复步骤|规范第|第\s*\d+\s*条"
    r"|否则归入|采购分类|题池归类)")

CITATION_LOOKBACK = 48
QUOTE_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"))


# ---------------------------------------------------------------- 工具

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _sentence_start(line, idx):
    """关键词之前、同一句的起点（句读符或行首）。

    只把真正的句读符当作边界；`|` / 制表符是**表格与排版分隔**，不是句子边界
    （`| ② 归入通用编码能力？ | **不归入**。` 这类表格行的否定词就在同一个单元格里，
    若把 `|` 当边界会把"不归入"切掉，造成漏判）。
    跨过装饰字符的工作交给 `_prefix_stripped`。
    """
    cut = 0
    for sep in ("。", "；", ";"):
        pos = line.rfind(sep, 0, idx)
        if pos + 1 > cut:
            cut = pos + 1
    return cut


def _prefix_stripped(line, idx, start):
    """关键词之前、跳过 Markdown 装饰字符后紧邻的那段文本（用于否定前缀判定）。

    只跨过**装饰字符**（`*`/空白/引号/括号/冒号/破折号…），并且在遇到**左侧引号或
    左括号**时立即停止 —— 否则会把引文里的内容一并算成"紧邻前缀"，把
    「…否则归入通用编码题池」这类**转述甲方条款**误判成自认。
    """
    i = idx
    while i > start and line[i - 1] in _SEPARATOR_CHARS:
        i -= 1
    if i > start and line[i - 1] in _LEFT_DELIMITERS:
        return ""
    return line[start:i]


def _context_flags(line, idx):
    """返回 (suppressed, reason)；只做可复算的子串判定。

    判定顺序（先判否定，再判引用）：
      1. 紧邻的否定式归类（`不归入` / `不主张`）
      2. 单个否定字与关键词之间只隔装饰字符（`**不归入**`）
      3. 处于直接引语内
      4. 命中点之前出现"转述甲方条款"的来源词

    **刻意不做**的事：不试图判断"归入 X？不归入"这种把否定词后置的表格行。
    这类句式里关键词本身在陈述句里成立，静态扫描无法与断言区分；
    见 `check_windows_mechanism.py` 里记录的人工复核口径（假阳性优先可见）。
    """
    start = _sentence_start(line, idx)
    stripped = _prefix_stripped(line, idx, start)

    if _NEGATION_PREFIX.search(stripped):
        return True, "否定前缀（在反驳归类，不是自认）"

    # 单个否定字与关键词之间只隔装饰字符（如 `**不归入**通用编码`）
    j = idx
    while j > start and line[j - 1] in _SEPARATOR_CHARS:
        j -= 1
    if j > start and line[j - 1] in _NEGATION_CHARS:
        return True, "否定前缀（在反驳归类，不是自认）"

    for opening, closing in QUOTE_PAIRS:
        if line.rfind(closing, start, idx) > line.rfind(opening, start, idx):
            return True, "处于直接引语内（转述，不是自认）"
    if _CITATION_CONTEXT.search(line[max(0, idx - CITATION_LOOKBACK):idx]):
        return True, "引用来源（转述甲方条款，不是自认）"
    return False, ""


# ---------------------------------------------------------------- 扫描

def scan_self_denial(root, extra_skip_dirs=(), extra_skip_files=(), include_suppressed=False):
    """扫描 root 下自述类文件中的自我否认表述。

    参数
    ----
    root                : 题包目录（或任意待扫目录）
    extra_skip_dirs     : 追加跳过的相对子树前缀（如 `environment/evidence`）
    extra_skip_files    : 追加跳过的**文件名**（不含路径）
    include_suppressed  : 是否返回被上下文判据抑制的条目（默认只返回真命中）

    返回 list[dict]，键：file / line / text / why / suppressed / suppress_reason。
    """
    hits = []
    skip_dirs = tuple(SCAN_SKIP_DIRS) + tuple(extra_skip_dirs)
    skip_files = set(SCAN_SKIP_FILES) | {str(x) for x in extra_skip_files}

    for dirpath, dirnames, filenames in os.walk(root):
        rel_root = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""
        dirnames[:] = [d for d in dirnames
                       if not any((rel_root + "/" + d).lstrip("/").startswith(s) for s in skip_dirs)]
        for name in sorted(filenames):
            rel = (rel_root + "/" + name).lstrip("/")
            if name in skip_files:
                continue
            if any(rel.startswith(s) for s in skip_dirs):
                continue
            if os.path.splitext(name)[1].lower() not in SCAN_SUFFIXES:
                continue
            text = read_text(os.path.join(dirpath, name))
            if not text:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern, why, _kind in SELF_DENIAL_PATTERNS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    try:
                        idx = match.start("anchor")
                    except IndexError:  # pragma: no cover - 防御：无 anchor 组时退回整段
                        idx = match.start()
                    suppressed, reason = _context_flags(line, idx)
                    if suppressed and not include_suppressed:
                        continue
                    hits.append({
                        "file": rel,
                        "line": lineno,
                        "text": line.strip()[:160],
                        "why": why,
                        "suppressed": suppressed,
                        "suppress_reason": reason,
                    })
    return hits


def format_hits(hits):
    """把命中列表压成 `文件:行号 [说明]` 的单行摘要（便于脚本打印）。"""
    return "; ".join("%s:%d %s" % (h["file"], h["line"], h["why"]) for h in hits)


if __name__ == "__main__":  # pragma: no cover - 便于手工抽查
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="自我否认 Windows 价值表述扫描")
    ap.add_argument("root", help="待扫目录（题包目录）")
    ap.add_argument("--include-suppressed", action="store_true")
    args = ap.parse_args()
    found = scan_self_denial(args.root, include_suppressed=args.include_suppressed)
    for hit in found:
        flag = " [suppressed: %s]" % hit["suppress_reason"] if hit["suppressed"] else ""
        print("%s:%d  %s%s" % (hit["file"], hit["line"], hit["why"], flag))
        if args.include_suppressed:
            print("    %s" % hit["text"])
    print("命中 %d 处" % sum(1 for h in found if not h["suppressed"]))
    sys.exit(1 if any(not h["suppressed"] for h in found) else 0)
