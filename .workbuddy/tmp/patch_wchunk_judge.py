# -*- coding: utf-8 -*-
"""wchunk-216 判分链路改造（第一波：run_tests.ps1 + required_testcases.json）。

从 wfmt-215 复制来的骨架需要全部改名换 id：
  run_tests.ps1  7 处字面替换 + slugByFunction 整块换成 18 条新映射
                 + task_id / task_version 改写
  required_testcases.json  15 条 -> 18 条（id 与 slug 严格一致）

pytest 函数名 -> check id 的约定（与 required 的 id 去掉 f2p-/p2p- 前缀一致）。
"""
import json
import pathlib
import re
import sys

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wchunk-216")
RUN = TASK / "tests" / "run_tests.ps1"
REQ = TASK / "tests" / "required_testcases.json"

# (pytest 函数名, check id 裸名, group)
CHECKS = [
    # ---- F2P：样本兼容 / 对齐 / 校验和 / 截断（候选必挂的核心）----
    ("test_sample_verifies", "sample-verifies", "F2P"),
    ("test_sample_roundtrip_byte_identical", "sample-roundtrip-byte-identical", "F2P"),
    ("test_sample_records_match_expected", "sample-records-match-expected", "F2P"),
    ("test_empty_sample_roundtrip", "empty-sample-roundtrip", "F2P"),
    ("test_record_alignment_is_eight_bytes", "record-alignment-is-eight-bytes", "F2P"),
    ("test_crc_matches_standard_check_value", "crc-matches-standard-check-value", "F2P"),
    ("test_tampered_content_is_rejected", "tampered-content-is-rejected", "F2P"),
    ("test_checksum_covers_header_and_records", "checksum-covers-header-and-records", "F2P"),
    ("test_truncated_container_reports_truncated", "truncated-container-reports-truncated", "F2P"),
    ("test_truncated_stream_reports_truncated", "truncated-stream-reports-truncated", "F2P"),
    # ---- P2P：错误分类 / 流式 / 不回归 ----
    ("test_bad_magic_reports_magic", "bad-magic-reports-magic", "P2P"),
    ("test_bad_version_reports_version", "bad-version-reports-version", "P2P"),
    ("test_verify_never_raises", "verify-never-raises", "P2P"),
    ("test_iter_records_is_streaming", "iter-records-is-streaming", "P2P"),
    ("test_self_roundtrip_small_records", "self-roundtrip-small-records", "P2P"),
    ("test_empty_payload_roundtrip", "empty-payload-roundtrip", "P2P"),
    ("test_generated_data_roundtrip_verified", "generated-data-roundtrip-verified", "P2P"),
    ("test_read_all_matches_unpack", "read-all-matches-unpack", "P2P"),
]


def patch_run_tests() -> None:
    text = RUN.read_text(encoding="utf-8")
    original = text

    # 1) 字面替换
    literal = [
        ("test_wfmt_semantics.py", "test_wchunk_semantics.py"),
        ("'wfmt'", "'wchunk'"),                       # 候选包目录检查
        ("wfmt-graded-", "wchunk-graded-"),
        ("`import wfmt` resolves", "`import wchunk` resolves"),
        ("task_id      = 'wfflab__wfmt-215'", "task_id      = 'wfflab__wchunk-216'"),
        ("task_version = '2.0.0'", "task_version = '1.0.0'"),
    ]
    for old, new in literal:
        if old in text:
            text = text.replace(old, new)
            print(f"  [OK] 字面替换: {old}")
        else:
            print(f"  [SKIP] 未命中: {old}")

    # 2) slugByFunction 整块
    start = text.index("$slugByFunction = [ordered]@{")
    end = text.index("}", text.index("'test_read_all_matches_unpack'", start))
    lines = ["    $slugByFunction = [ordered]@{"]
    for func, slug, _group in CHECKS:
        lines.append(f"        '{func}'".ljust(52) + f"= '{slug}'")
    lines.append("    }")
    block = "\n".join(lines)
    text = text[:start] + block + text[end + 1:]
    print(f"  [OK] slugByFunction -> {len(CHECKS)} 条映射")

    if text == original:
        print("  [WARN] 无变化")
    RUN.write_text(text, encoding="utf-8", newline="\n")
    print(f"[OK] {RUN.name} 已写入（{len(text.splitlines())} 行）")


def patch_required() -> None:
    items = [{"id": f"{'f2p' if g == 'F2P' else 'p2p'}-{slug}", "group": g}
             for _f, slug, g in CHECKS]
    REQ.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    f2p = sum(1 for i in items if i["group"] == "F2P")
    p2p = sum(1 for i in items if i["group"] == "P2P")
    print(f"[OK] {REQ.name} -> {len(items)} 条（F2P {f2p} / P2P {p2p}）")


def verify() -> int:
    """交叉校验：required 的裸 id 必须全部出现在 run_tests.ps1 的映射里。"""
    text = RUN.read_text(encoding="utf-8")
    missing = []
    for _f, slug, _g in CHECKS:
        if f"'{slug}'" not in text:
            missing.append(slug)
    req = json.loads(REQ.read_text(encoding="utf-8"))
    bad = [i for i in req if i["id"].split("-", 1)[1] not in
           {s for _f, s, _g in CHECKS}]
    if missing or bad:
        print(f"[FAIL] 映射缺失={missing}  required 越界={bad}")
        return 1
    print(f"[VERIFY] {len(CHECKS)} 条映射与 required 完全一致")
    return 0


def main() -> int:
    patch_run_tests()
    patch_required()
    return verify()


if __name__ == "__main__":
    sys.exit(main())
