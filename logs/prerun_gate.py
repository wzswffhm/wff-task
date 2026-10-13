# -*- coding: utf-8 -*-
"""prerun_gate.py -- 跑分前一键门禁。

依次执行：
  1. local_checks        —— 身份位一致、绑定、封印清单、隔离、负访问
  2. static_qc           —— 甲方 inspect_delivery + 判分配置 + 文档版本陈述
  3. hygiene_check       —— 旧数据残留、jobs 单一 checksum、章节引用悬空
  4. simulate_grade      —— 判分链模拟（真跑 run_tests.ps1，oracle 与 no-change 两端）

任何一步失败就中止并报出，避免把「跑完 40 分钟才发现」的问题带到跑分里。

用法：
    python prerun_gate.py --task 219
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

LOGS = Path(r"C:\Users\Administrator\Desktop\wff-task\logs")
REL = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
           r"\relaunch-20261013")
STAGED = REL / "staged"

TASKS = {
    "218": {"pkg": "wfflab__wlogseg-218-v1.1.0-delivery", "version": "1.1.0"},
    "219": {"pkg": "wfflab__wpeimg-219-v1.4.0-delivery", "version": "1.4.0"},
}

PY = sys.executable


def run(label: str, args: list[str], expect_zero: bool = True) -> tuple[bool, str]:
    print("\n" + "=" * 76)
    print("▶ %s" % label)
    print("=" * 76)
    proc = subprocess.run([PY] + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.strip().splitlines()[-14:]:
        print("  %s" % line)
    ok = (proc.returncode == 0) if expect_zero else True
    print("  → exit=%d %s" % (proc.returncode, "OK" if ok else "FAILED"))
    return ok, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = STAGED / cfg["pkg"]
    if not pkg.is_dir():
        raise SystemExit("package not found: %s" % pkg)

    results = []
    ok, out = run("1/4 local_checks（身份/绑定/封印/隔离/负访问）",
                  [str(LOGS / "local_checks.py"), "--task", str(pkg),
                   "--expect-version", cfg["version"]])
    results.append(("local_checks", ok))
    if not ok:
        return 1

    ok, _ = run("2/4 static_qc（甲方交付目录检查 + 判分配置 + 文档版本）",
                [str(LOGS / "static_qc.py"), "--task", a.task])
    results.append(("static_qc", ok))
    if not ok:
        return 1

    ok, _ = run("3/4 hygiene_check（旧数据残留 / jobs 一致性 / 章节引用）",
                [str(LOGS / "hygiene_check.py"), "--task", a.task])
    results.append(("hygiene_check", ok))
    if not ok:
        return 1

    ok, _ = run("4/4 simulate_grade（判分链：oracle 端）",
                [str(LOGS / "simulate_grade.py"), "--task", a.task])
    results.append(("simulate_grade_oracle", ok))
    if not ok:
        return 1

    # the no-change side is expected to FAIL tests, so its exit code is 1 when
    # the chain works: treat "exit != 0" as the healthy outcome and only reject
    # a chain-level error (ModuleNotFoundError / no tests collected).
    ok2, out2 = run("4b/4 simulate_grade（判分链：no-change 端，失败才是对的）",
                    [str(LOGS / "simulate_grade.py"), "--task", a.task, "--candidate"],
                    expect_zero=False)
    chain_broken = ("ModuleNotFoundError" in out2) or ("no tests ran" in out2)
    results.append(("simulate_grade_nochange", not chain_broken))
    if chain_broken:
        print("\n判分链在 no-change 端出现链路级错误，中止。")
        return 1

    print("\n" + "=" * 76)
    bad = [n for n, ok_ in results if not ok_]
    if bad:
        print("跑分前门禁 FAILED: %s" % ", ".join(bad))
        return 1
    print("跑分前门禁全部 PASSED —— 可以启动跑分")
    print("提示：启动前请用 static_qc 输出的冻结 dirhash 核对首轮 job 的 checksum。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
