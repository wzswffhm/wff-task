#!/usr/bin/env python3
"""检查 proposal.json 的可读文字是否为自然、口语化的中文。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator


CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_TOKEN_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_+.-]*\b")
FENCE_PATTERN = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
URL_PATTERN = re.compile(
    r"(?:https?|git|ssh)://[^\s<>\"'，。；：！？）】]+", re.IGNORECASE
)
HASH_PATTERN = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{7,64}(?![A-Za-z0-9])")
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


def visible_prose(value: str) -> str:
    text = FENCE_PATTERN.sub("", value)
    text = INLINE_CODE_PATTERN.sub("", text)
    text = URL_PATTERN.sub("", text)
    text = HASH_PATTERN.sub("", text)
    return text


def iter_human_fields(document: dict[str, Any]) -> Iterator[tuple[str, str]]:
    proposal = document.get("proposal")
    if isinstance(proposal, dict):
        for field in (
            "A_modification_idea",
            "B_modification_details",
            "C_agent_task",
        ):
            value = proposal.get(field)
            if isinstance(value, str):
                yield f"$.proposal.{field}", value
        difficulties = proposal.get("D_task_difficulties")
        if isinstance(difficulties, list):
            for index, value in enumerate(difficulties):
                if isinstance(value, str):
                    yield f"$.proposal.D_task_difficulties[{index}]", value
    for field in (
        "proposal_sources",
        "proposal_scene",
        "proposal_verify",
        "expert_experience_skill",
    ):
        value = document.get(field)
        if isinstance(value, str):
            yield f"$.{field}", value


def long_segments(text: str, limit: int = 180) -> list[str]:
    segments = [segment.strip() for segment in re.split(r"[。！？；\n]+", text)]
    return [segment for segment in segments if len(segment) > limit]


def analyze_proposal_language(document: Any) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    if not isinstance(document, dict):
        return {
            "ok": False,
            "issues": [
                {
                    "code": "invalid_document",
                    "location": "$",
                    "message": "proposal.json 顶层必须是对象",
                }
            ],
        }

    scanned_fields = 0
    cjk_chars = 0
    for location, raw_value in iter_human_fields(document):
        scanned_fields += 1
        prose = visible_prose(raw_value)
        cjk_chars += len(CJK_PATTERN.findall(prose))
        if not CJK_PATTERN.search(prose):
            issues.append(
                {
                    "code": "missing_chinese_prose",
                    "location": location,
                    "message": "面向人的说明必须使用中文",
                }
            )
        latin_tokens = LATIN_TOKEN_PATTERN.findall(prose)
        if latin_tokens:
            preview = "、".join(dict.fromkeys(latin_tokens[:6]))
            issues.append(
                {
                    "code": "english_in_prose",
                    "location": location,
                    "message": (
                        f"发现未包裹的英文：{preview}；技术标识请放进反引号，"
                        "其余内容改成中文"
                    ),
                }
            )
        found_phrases = [phrase for phrase in AI_PHRASES if phrase in prose]
        if found_phrases:
            issues.append(
                {
                    "code": "ai_tone",
                    "location": location,
                    "message": "发现模板化表达：" + "、".join(found_phrases[:4]),
                }
            )
        connector_count = sum(prose.count(word) for word in FORMULAIC_CONNECTORS)
        if connector_count >= 2:
            issues.append(
                {
                    "code": "formulaic_sequence",
                    "location": location,
                    "message": (
                        "连续使用“首先、其次、再次、最后”会显得像模板，"
                        "请直接写具体动作和判断依据"
                    ),
                }
            )
        if long_segments(prose):
            issues.append(
                {
                    "code": "overlong_sentence",
                    "location": location,
                    "message": "单句过长，请拆成更直接、口语化的短句",
                }
            )

    expert = document.get("expert_experience_skill")
    if isinstance(expert, str):
        expert_prose = visible_prose(expert)
        marker_count = sum(expert_prose.count(marker) for marker in PRACTICAL_MARKERS)
        if marker_count < 2:
            issues.append(
                {
                    "code": "stiff_expert_voice",
                    "location": "$.expert_experience_skill",
                    "message": (
                        "专家经验要像工程师在讲自己的做法，至少使用两处“我会、"
                        "我一般、先、再、遇到、最容易、不要、可以”等自然表达"
                    ),
                }
            )

    return {
        "ok": not issues,
        "issues": issues,
        "scanned_fields": scanned_fields,
        "cjk_chars": cjk_chars,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    path = args.proposal.expanduser().resolve()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 {path}: {exc}") from exc
    result = analyze_proposal_language(document)
    result["path"] = str(path)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for issue in result["issues"]:
            print(f"[FAIL] {issue['location']}：{issue['message']}")
        if result["ok"]:
            print(
                "[PASS] proposal.json 的说明文字为自然中文："
                f"检查 {result['scanned_fields']} 个字段，汉字 {result['cjk_chars']} 个"
            )
        print("Result: " + ("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
