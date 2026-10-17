# -*- coding: utf-8 -*-
"""生成两包的“作者用例设计 + 构建时间线”证据包（VV-24 / VV-25 / VV-35）。

重要：本证据包是 2026-10-16 由交付方**事后整理**的，用于把
instruction 的验收条款 ↔ 隐藏用例 ↔ 期望/拒绝条件对齐，并把可核验的
构建时间线一并留档。它**不是**原始造测会话，也不能替代原始会话：
原始造测可见会话在本机 DSH 会话存档中不存在（见 README）。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import subprocess

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = REPO / "harbor-windows"
GENERATED = "2026-10-16"

# --------------------------------------------------------------------------- 215
WSPARSE_CASES = [
    ("preallocate-marks-file-sparse", "F2P", "A", "preallocate 后文件带 sparse 属性（sparse_state/属性位/fsutil 三路一致）", "不是稀疏文件", "test_preallocate_marks_file_sparse"),
    ("preallocate-does-not-materialise-the-file", "F2P", "A", "预分配 1 GiB 后逻辑长度精确等于 1 GiB，而物理占用 < 8 MiB", "把整份文件写实（物理占用≈逻辑长度）", "test_preallocate_does_not_materialise_the_file"),
    ("written-extent-is-the-only-allocation", "F2P", "B / D", "只有真正写入的两处区域被报告为已分配，其余是空洞", "返回整段 (0, size)", "test_written_extent_is_the_only_allocation"),
    ("disk-usage-is-physical-not-logical", "F2P", "C", "disk_usage 与文件系统给出的物理占用一致（容差 ≤64 KiB）", "返回逻辑长度", "test_disk_usage_is_physical_not_logical"),
    ("allocated-ranges-are-the-real-extents", "F2P", "D", "候选区间与评测器用 FSCTL_QUERY_ALLOCATED_RANGES 独立量到的簇级区间一致", "只覆盖写入点、长度差 1 字节（8193 vs 8192）也算不过", "test_allocated_ranges_are_the_real_extents"),
    ("hole-only-file-has-no-allocated-range", "F2P", "D", "全空洞文件 disk_usage=0 且 allocated_ranges=[]", "返回非空区间或非零占用", "test_hole_only_file_has_no_allocated_range"),
    ("sparse-flag-is-actually-set", "F2P", "E", "对密集文件设 sparse_flag 后属性真的置位（三路一致）", "只返回 True 而属性未变", "test_sparse_flag_is_actually_set"),
    ("late-sparse-flag-does-not-free-clusters", "F2P", "E", "已扩展成密集的文件补设 sparse 后不得谎报成功，占用仍反映真实密集量", "返回成功且占用骤降", "test_late_sparse_flag_does_not_free_clusters"),
    ("disk-usage-of-a-directory-is-unsupported", "F2P", "F", "目录路径 → WSParseError(kind='unsupported')", "静默成功或裸 OSError", "test_disk_usage_of_a_directory_is_unsupported"),
    ("allocated-ranges-of-a-directory-is-unsupported", "F2P", "F", "目录路径 → WSParseError(kind='unsupported')", "静默成功或裸 OSError", "test_allocated_ranges_of_a_directory_is_unsupported"),
    ("preallocated-tail-is-readable-as-zeros", "P2P", "B", "预分配留出的空洞读出全零", "空洞读出非零或读失败", "test_preallocated_tail_is_readable_as_zeros"),
    ("preallocate-returns-the-length", "P2P", "A", "preallocate 返回目标长度", "返回 None 或错误长度", "test_preallocate_returns_the_length"),
    ("preallocate-is-idempotent", "P2P", "A", "重复预分配同一路径语义不变", "第二次调用改变长度/占用", "test_preallocate_is_idempotent"),
    ("preallocate-never-shrinks", "P2P", "A", "对更小的 size 再次预分配不得截断已有文件", "把文件截短", "test_preallocate_never_shrinks"),
    ("preallocate-rejects-a-negative-size", "P2P", "F", "负数 size → WSParseError(kind='badarg')", "静默接受或抛裸 OSError", "test_preallocate_rejects_a_negative_size"),
    ("disk-usage-of-a-dense-file-is-about-its-length", "P2P", "C", "密集文件 disk_usage ≈ 逻辑长度", "把密集文件报成接近 0", "test_disk_usage_of_a_dense_file_is_about_its_length"),
    ("allocated-ranges-are-ordered-and-inside-the-file", "P2P", "D", "区间按 offset 升序、互不重叠、完全落在文件长度内", "顺序错乱或越界", "test_allocated_ranges_are_ordered_and_inside_the_file"),
    ("allocated-ranges-of-an-empty-file-is-empty", "P2P", "D", "空文件返回空列表", "返回区间", "test_allocated_ranges_of_an_empty_file_is_empty"),
    ("sparse-state-of-a-fresh-file-is-a-boolean", "P2P", "G", "sparse_state 返回布尔", "返回非布尔/抛异常", "test_sparse_state_of_a_fresh_file_is_a_boolean"),
    ("visible-smoke-suite-still-passes", "P2P", "G", "工作区可见冒烟测试 tests/test_wsparse_basic.py 全部通过", "回归破坏", "test_visible_smoke_suite_still_passes"),
]

# --------------------------------------------------------------------------- 216
WVAS_CASES = [
    ("region-addresses-are-64-bit", "F2P", "A", "regions().base 与 VirtualQueryEx 同一时刻的 BaseAddress 逐个一致（不截断到 32 位）", "高地址区间被截断/取整", "test_region_addresses_are_64_bit"),
    ("region-sizes-are-64-bit", "F2P", "A", "regions().size 与 VirtualQueryEx 的 RegionSize 逐个一致（含 6 GiB 保留段）", "长度被截断成小数值", "test_region_sizes_are_64_bit"),
    ("reserved-regions-are-reported", "F2P", "A", "include_reserved=True 时 MEM_RESERVE 区间必须出现且 state='reserve'", "只报 commit，保留段消失", "test_reserved_regions_are_reported"),
    ("file-mapping-path-is-a-dos-path", "F2P", "B.1 / B.2", "文件映射区间 path 是可打开的 DOS/UNC 路径且等于真实磁盘路径", "返回 \\Device\\... / \\??\\... 形式", "test_file_mapping_path_is_a_dos_path"),
    ("device-paths-are-translated", "F2P", "B.1", "NT 设备路径被翻译成盘符或 UNC", "原样透出设备路径", "test_device_paths_are_translated"),
    ("anonymous-mapping-has-no-path", "F2P", "B.3", "匿名映射 path 必须是 None", "返回空字符串或占位文本", "test_anonymous_mapping_has_no_path"),
    ("missing-process-is-classified", "F2P", "D", "不存在的 pid → WVasError(kind='no-such-process')", "裸 OSError 或错误 kind", "test_missing_process_is_classified"),
    ("modules-are-deduplicated", "F2P", "C", "同一映像文件的多个 region 在 modules() 中只出现一次", "同一路径重复出现", "test_modules_are_deduplicated"),
    ("file-backed-regions-are-a-subset", "F2P", "B.4", "file_backed_regions 必须返回 regions() 中**全部** path 非 None 的项，且保持 regions() 顺序", "返回空列表[]、漏项或多出非背衬项", "test_file_backed_regions_are_a_subset"),
    ("regions-are-sorted-by-base", "P2P", "A", "regions 按 base 升序", "顺序不定", "test_regions_are_sorted_by_base"),
    ("region-records-are-well-formed", "P2P", "A / E", "每条记录恰好含 base/size/state/type/protect/path/image 且类型正确", "缺字段或类型错误", "test_region_records_are_well_formed"),
    ("own-process-reports-image-regions", "P2P", "C", "调用方自身进程能报出 image 区间", "报不出映像", "test_own_process_reports_image_regions"),
    ("include-reserved-false-only-reports-committed-memory", "P2P", "A", "include_reserved=False 时只剩 state='commit'", "仍含 reserve", "test_include_reserved_false_only_reports_committed_memory"),
    ("negative-pid-is-rejected", "P2P", "D", "负数 pid → WVasError(kind='badarg')", "裸异常或错误 kind", "test_negative_pid_is_rejected"),
    ("modules-are-sorted-by-base", "P2P", "C", "modules 按 base 升序", "顺序不定", "test_modules_are_sorted_by_base"),
    ("visible-smoke-suite-still-passes", "P2P", "E.2", "可见冒烟测试 tests/test_wvas_basic.py 全部通过", "回归破坏", "test_visible_smoke_suite_still_passes"),
]

PACKAGES = {
    "wfflab__wsparse-215-v1.0.0-delivery": {
        "task_id": "wfflab__wsparse-215",
        "version": "1.0.0",
        "suite": "tests/test_wsparse_semantics.py",
        "instruction": "instruction.md",
        "cases": WSPARSE_CASES,
        "clauses": "instruction.md A 稀疏预分配 / B 写入语义 / C 占用统计 / D 已分配区间 / E 顺序语义 / F 错误分类 / G 不得回归",
    },
    "wfflab__wvas-216-v1.0.0-delivery": {
        "task_id": "wfflab__wvas-216",
        "version": "1.0.0",
        "suite": "tests/test_wvas_semantics.py",
        "instruction": "instruction.md",
        "cases": WVAS_CASES,
        "clauses": "instruction.md A 区间描述 / B 文件背衬与路径 / C 模块清单 / D 错误分类 / E 边界与回归",
    },
}


def git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    return out.stdout.strip()


def first_add(rel: str) -> dict:
    line = git("log", "--diff-filter=A", "--follow", "--format=%H|%ai|%s",
               "--", f"harbor-windows/{rel}")
    if not line:
        return {}
    commit, when, subject = line.split("\n")[-1].split("|", 2)
    return {"commit": commit, "when": when, "subject": subject}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


README = """# 作者用例设计对照与构建时间线（交付方整理）

> **性质声明（务必先读）**
>
> 本目录是 **2026-10-16 由交付方事后整理**的证据包，用于把 `instruction.md`
> 的验收条款 ↔ 隐藏用例 ↔ 每条用例的**期望结果 / 拒绝条件**对齐，并把可核验的
> 构建时间线留档。
>
> 它**不是**原始造测会话，也**不能**替代原始造测会话。交付方已穷尽检索本机
> DSH 会话存档（`%USERPROFILE%\\.dsh\\sessions`，5 个工作目录 / 30 个会话文件，
> 42.9 MB 压缩），**没有任何会话包含写入本包隐藏套件的事件**：这两个题包的造题
> 过程没有留在本机会话存档中。按甲方要求“不能事后补写成旧记录”，本目录不含
> 任何伪造的会话记录、时间戳或消息。

## 内容

| 文件 | 是什么 | 能证明什么 / 不能证明什么 |
|---|---|---|
| `contract-map.json` | 每条隐藏用例 → 题面条款 → 期望行为 / 拒绝条件 → 分组（F2P/P2P） | 能证明**设计是围绕题面契约预先定义**的（每条用例都有对应条款与拒绝条件）；**不能**证明作者在写测试之前口头描述过它 |
| `timeline.json` | 题面、隐藏套件、评测链路进入版本库的提交与时间，以及 job 记录时间 | 能提供**可核验的时间顺序与哈希**；**不能**替代原始会话 |
| `sources.json` | 本目录引用的每个来源文件及其 SHA-256 | 便于复核引用是否与当前包一致 |

## 预处理说明

- 时间线取自本仓库 git 历史（`--diff-filter=A --follow`），时间为提交者时间。
- `contract-map.json` 的条款号直接引用 `instruction.md` 的 A–G / A–E 小节标题。
- 隐藏用例名为 `tests/` 与 `verifier/tests/` 两份**逐字节一致**的副本中的函数名。
- 本目录不进入 agent 容器：`environment/Dockerfile` 只 `COPY workspace/`。
"""


def main() -> int:
    for pkg, meta in PACKAGES.items():
        root = HW / pkg
        out = root / "evidence" / "author-design"
        out.mkdir(parents=True, exist_ok=True)

        contract = {
            "schema": "author-contract-map-v1",
            "generated": GENERATED,
            "generated_by": "delivery-side (post-hoc alignment, not the original authoring session)",
            "task_id": meta["task_id"],
            "task_version": meta["version"],
            "instruction": meta["instruction"],
            "clauses": meta["clauses"],
            "hidden_suite": meta["suite"],
            "cases": [
                {
                    "case_id": cid,
                    "group": group,
                    "instruction_clause": clause,
                    "expected": expected,
                    "rejection_condition": rejection,
                    "hidden_test": test,
                }
                for cid, group, clause, expected, rejection, test in meta["cases"]
            ],
        }
        (out / "contract-map.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        timeline = {
            "schema": "author-timeline-v1",
            "generated": GENERATED,
            "task_id": meta["task_id"],
            "note": "Git history only; the original authoring session is not available.",
            "first_added": {},
            "current_hashes": {},
        }
        for rel in (meta["instruction"], "task.toml", "tests/run_tests.ps1",
                    "tests/aggregate_results.ps1", meta["suite"],
                    "verifier/tests/" + pathlib.Path(meta["suite"]).name,
                    "tests/required_testcases.json", "tests/rubric.json",
                    "tests/judge.toml", "verifier/README.md", "metadata/windows_mechanism.json"):
            timeline["first_added"][rel] = first_add(f"{pkg}/{rel}")
            path = root / rel
            timeline["current_hashes"][rel] = (
                {"sha256": sha256(path), "size": path.stat().st_size} if path.is_file() else None)

        jobs = root / "jobs"
        stamps = []
        if jobs.is_dir():
            for d in sorted(p for p in jobs.iterdir() if p.is_dir() and p.name != "_index"):
                r = d / "result.json"
                if r.is_file():
                    stamps.append({"job": d.name, "mtime": dt.datetime.fromtimestamp(
                        r.stat().st_mtime).isoformat(timespec="seconds")})
        timeline["job_result_mtimes"] = stamps
        (out / "timeline.json").write_text(
            json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        sources = {
            "schema": "author-sources-v1",
            "generated": GENERATED,
            "task_id": meta["task_id"],
            "sources": [
                {"path": rel, "sha256": sha256(root / rel)}
                for rel in (meta["instruction"], "task.toml", meta["suite"],
                            "verifier/tests/" + pathlib.Path(meta["suite"]).name,
                            "tests/required_testcases.json", "tests/rubric.json",
                            "metadata/windows_mechanism.json")
                if (root / rel).is_file()
            ],
        }
        (out / "sources.json").write_text(
            json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "README.md").write_text(README, encoding="utf-8")
        print("written:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
