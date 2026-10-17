# -*- coding: utf-8 -*-
"""准备 216 的“fixture setup 阶段报错”探针（甲方第 3 条）。

旧链路把 outcome="error" 当成候选 FAIL，于是整轮变成 VALID / 0 分；
新链路必须把它保留成 INVALID。
"""
from __future__ import annotations

import pathlib
import subprocess

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = "wfflab__wvas-216-v1.0.0-delivery"
BASE = REPO / "harbor-windows" / "_qc_runs" / "wvas216-fix"
REV = "1568cfb3"

FUNCS = [
    "test_region_addresses_are_64_bit",
    "test_region_sizes_are_64_bit",
    "test_reserved_regions_are_reported",
    "test_file_mapping_path_is_a_dos_path",
    "test_device_paths_are_translated",
    "test_anonymous_mapping_has_no_path",
    "test_missing_process_is_classified",
    "test_modules_are_deduplicated",
    "test_regions_are_sorted_by_base",
    "test_region_records_are_well_formed",
    "test_own_process_reports_image_regions",
    "test_file_backed_regions_are_a_subset",
    "test_include_reserved_false_only_reports_committed_memory",
    "test_negative_pid_is_rejected",
    "test_modules_are_sorted_by_base",
    "test_visible_smoke_suite_still_passes",
]


def show(rel: str, dest: pathlib.Path) -> None:
    out = subprocess.run(["git", "-C", str(REPO), "show", f"{REV}:{rel}"],
                         capture_output=True, check=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out.stdout)
    print(f"{rel} -> {dest} ({len(out.stdout)} B)")


def main() -> int:
    old = BASE / "old-harness"
    show(f"harbor-windows/{PKG}/tests/run_tests.ps1", old / "run_tests.ps1")
    show(f"harbor-windows/{PKG}/tests/aggregate_results.ps1", old / "aggregate_results.ps1")

    suite = BASE / "error-verifier" / "tests" / "test_wvas_semantics.py"
    suite.parent.mkdir(parents=True, exist_ok=True)
    body = [
        '"""Probe suite: every case fails during fixture setup.',
        '',
        'This is the reviewer probe for "an independent fixture raises in setup":',
        'pytest reports outcome="error" for every case, so the run carries no',
        'information about the candidate and must be INVALID, never a 0.',
        '"""',
        'import pytest',
        '',
        '',
        '@pytest.fixture(autouse=True)',
        'def infrastructure_fault():',
        '    raise RuntimeError("simulated infrastructure fault during setup")',
        '',
    ]
    body += [f"def {name}():\n    pass\n" for name in FUNCS]
    suite.write_text("\n".join(body), encoding="utf-8")
    print("error suite ->", suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
