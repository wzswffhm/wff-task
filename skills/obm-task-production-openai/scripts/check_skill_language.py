#!/usr/bin/env python3
"""检查 OBM 专家 SKILL.md 是否使用中文撰写。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")
ENGLISH_WORD_PATTERN = re.compile(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)*\b")
FENCE_PATTERN = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
URL_PATTERN = re.compile(r"https?://\S+")
MARKDOWN_LINK_TARGET_PATTERN = re.compile(r"\]\([^)]*\)")
AI_PHRASES = (
    "本文将",
    "本文主要",
    "以下将",
    "下面将",
    "综上所述",
    "总而言之",
    "值得注意的是",
    "需要注意的是",
    "不难发现",
    "显而易见",
    "旨在",
    "通过上述",
    "在实际应用中",
    "至关重要",
    "不可或缺",
    "提供有力保障",
    "显著提升",
    "全面提升",
)
PRACTICAL_MARKERS = (
    "我一般",
    "我会",
    "我的做法",
    "实际做的时候",
    "遇到",
    "最容易",
    "先",
    "再",
    "别",
    "不要",
    "可以",
)
FORMULAIC_CONNECTORS = ("首先", "其次", "再次", "最后")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    match = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if not match:
        return "", text
    return match.group(1), text[match.end() :]


def prose_without_code(body: str) -> str:
    value = FENCE_PATTERN.sub("\n", body)
    value = INLINE_CODE_PATTERN.sub("", value)
    value = URL_PATTERN.sub("", value)
    value = MARKDOWN_LINK_TARGET_PATTERN.sub("]", value)
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    return value


def analyze_skill_language(text: str) -> dict[str, Any]:
    frontmatter, body = split_frontmatter(text)
    prose = prose_without_code(body)
    issues: list[str] = []

    description_match = re.search(
        r"(?m)^description\s*:\s*[\"']?(.*?)[\"']?\s*$", frontmatter
    )
    if not description_match:
        issues.append("frontmatter 缺少 description")
    elif not CJK_PATTERN.search(description_match.group(1)):
        issues.append("frontmatter 的 description 必须使用中文")
    else:
        description_prose = INLINE_CODE_PATTERN.sub("", description_match.group(1))
        description_english = ENGLISH_WORD_PATTERN.findall(description_prose)
        if description_english:
            preview = "、".join(dict.fromkeys(description_english[:6]))
            issues.append(
                "frontmatter 的 description 存在未包裹英文："
                f"{preview}；技术标识请放进反引号"
            )
        description_ai = [
            phrase for phrase in AI_PHRASES if phrase in description_prose
        ]
        if description_ai:
            issues.append(
                "frontmatter 的 description 存在模板化表达："
                + "、".join(description_ai[:4])
            )

    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", prose)
    if not headings:
        issues.append("正文缺少 Markdown 标题")
    else:
        english_headings = [heading for heading in headings if not CJK_PATTERN.search(heading)]
        if english_headings:
            preview = "；".join(english_headings[:3])
            issues.append(f"Markdown 标题必须包含中文：{preview}")

    cjk_chars = len(CJK_PATTERN.findall(prose))
    latin_chars = len(LATIN_PATTERN.findall(prose))
    language_chars = cjk_chars + latin_chars
    chinese_ratio = cjk_chars / language_chars if language_chars else 0.0

    if cjk_chars < 120:
        issues.append(f"中文正文过少，仅检测到 {cjk_chars} 个汉字")
    if language_chars and chinese_ratio < 0.30:
        issues.append(
            "正文不是以中文为主："
            f"汉字占中英文字符的 {chinese_ratio:.1%}，最低要求为 30%"
        )

    english_prose_lines: list[str] = []
    prose_line_count = 0
    chinese_line_count = 0
    for raw_line in prose.splitlines():
        line = re.sub(r"^\s*(?:#{1,6}|[-*+] |\d+[.)] )\s*", "", raw_line).strip()
        if not line or re.fullmatch(r"[-=_:|\s]+", line):
            continue
        words = ENGLISH_WORD_PATTERN.findall(line)
        cjk = CJK_PATTERN.findall(line)
        if not words and not cjk:
            continue
        prose_line_count += 1
        if cjk:
            chinese_line_count += 1
        elif len(words) >= 6:
            english_prose_lines.append(line)

    if english_prose_lines:
        preview = "；".join(english_prose_lines[:3])
        issues.append(f"发现纯英文说明行，请改写为中文：{preview}")

    english_tokens = ENGLISH_WORD_PATTERN.findall(prose)
    if english_tokens:
        preview = "、".join(dict.fromkeys(english_tokens[:8]))
        issues.append(
            "正文存在未包裹的英文："
            f"{preview}；技术标识请放进反引号，其余说明改成中文"
        )

    found_phrases = [phrase for phrase in AI_PHRASES if phrase in prose]
    if found_phrases:
        issues.append("发现模板化表达：" + "、".join(found_phrases[:6]))

    connector_count = sum(prose.count(word) for word in FORMULAIC_CONNECTORS)
    if connector_count >= 2:
        issues.append(
            "连续使用“首先、其次、再次、最后”会显得像模板，请直接写具体动作和判断依据"
        )

    marker_count = sum(prose.count(marker) for marker in PRACTICAL_MARKERS)
    if marker_count < 2:
        issues.append(
            "正文语气过于书面或模板化；请像工程师交流经验一样表达，至少使用两处"
            "“我会、我一般、先、再、遇到、最容易、不要、可以”等自然说法"
        )

    long_sentences = [
        segment.strip()
        for segment in re.split(r"[。！？；\n]+", prose)
        if len(segment.strip()) > 180
    ]
    if long_sentences:
        issues.append("存在超过 180 字的长句，请拆成更直接、口语化的短句")

    chinese_line_ratio = (
        chinese_line_count / prose_line_count if prose_line_count else 0.0
    )
    if prose_line_count and chinese_line_ratio < 0.60:
        issues.append(
            "中文说明行不足："
            f"{chinese_line_count}/{prose_line_count} 行包含中文，最低要求为 60%"
        )

    return {
        "ok": not issues,
        "issues": issues,
        "cjk_chars": cjk_chars,
        "latin_chars": latin_chars,
        "chinese_ratio": round(chinese_ratio, 6),
        "prose_lines": prose_line_count,
        "chinese_lines": chinese_line_count,
        "chinese_line_ratio": round(chinese_line_ratio, 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", type=Path, help="要检查的 SKILL.md")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    path = args.skill.expanduser().resolve()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"无法读取 {path}: {exc}") from exc

    result = analyze_skill_language(text)
    result["path"] = str(path)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for issue in result["issues"]:
            print(f"[FAIL] {issue}")
        if result["ok"]:
            print(
                "[PASS] 专家 SKILL.md 为中文文档："
                f"汉字 {result['cjk_chars']}，英文字母 {result['latin_chars']}，"
                f"中文说明行 {result['chinese_lines']}/{result['prose_lines']}"
            )
        print("Result: " + ("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
