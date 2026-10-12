# -*- coding: utf-8 -*-
"""verify_218_delivery.py —— 交付 ZIP 自检（不回写、不改包）。

检查项：
  1. sha256 与同名 .sha256 文件一致；
  2. zip 顶层只有单一同名目录，二层与 215/216 同构（7 项）；
  3. jobs/ 恰好 14 个 trial，每个含 config.json/result.json/agent/verifier；
  4. 关键件存在：instruction.md、task.toml、solution/{README.md,solve.ps1,solve.bat}、
     tests/{test.ps1,rubric.json,judge.toml,required_testcases.json}、verifier/{SEALED_MANIFEST.json,rubric.conditions.json}；
  5. 禁止项：extras/、__pycache__、*.pyc、__MACOSX、.pytest_cache；
  6. 包内 jobs 汇总分数与控制轮结果与预期一致。

用法：python verify_218_delivery.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
DELIV = ROOT / "deliverables" / "2026-10-12_wlogseg218-交付"
ZIP = DELIV / "package" / "wfflab__wlogseg-218-v1.0.0-delivery.zip"
ROOT_NAME = "wfflab__wlogseg-218-v1.0.0-delivery"
EXPECTED_L2 = {"environment", "instruction.md", "jobs", "solution", "task.toml",
               "tests", "verifier"}
FORBIDDEN_PARTS = {"extras", "__pycache__", ".pytest_cache", "__MACOSX", ".mypy_cache"}

REQUIRED = [
    "instruction.md", "task.toml",
    "solution/README.md", "solution/solve.ps1", "solution/solve.bat",
    "tests/test.ps1", "tests/test.bat", "tests/rubric.json", "tests/judge.toml",
    "tests/required_testcases.json", "tests/run_tests.ps1", "tests/aggregate_results.ps1",
    "verifier/SEALED_MANIFEST.json", "verifier/rubric.conditions.json",
    "verifier/tests/test_wlogseg_semantics.py",
    "environment/Dockerfile", "environment/adapter.toml", "environment/run.ps1",
    "environment/workspace/wlogseg/codec.py", "environment/workspace/pyproject.toml",
    "jobs/config.json", "jobs/result.json", "jobs/lock.json", "jobs/README.md",
]


def main() -> int:
    fails, warns = [], []
    if not ZIP.is_file():
        print("!! 缺 zip：%s" % ZIP)
        return 2

    digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    side = ZIP.with_suffix(ZIP.suffix + ".sha256")
    side_digest = side.read_text(encoding="ascii").split()[0] if side.is_file() else None
    print("zip        : %s (%d bytes)" % (ZIP.name, ZIP.stat().st_size))
    print("sha256     : %s" % digest)
    if side_digest != digest:
        fails.append("sha256 与 .sha256 文件不一致（%s）" % side_digest)

    with zipfile.ZipFile(ZIP) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        bad = sorted({p for n in names for p in n.split("/") if p in FORBIDDEN_PARTS})
        if bad:
            fails.append("含禁止项：%s" % bad)
        tops = sorted({n.split("/")[0] for n in names})
        if tops != [ROOT_NAME]:
            fails.append("顶层不是单一同名目录：%s" % tops)
        l2 = sorted({n.split("/")[1] for n in names if len(n.split("/")) > 1})
        if set(l2) != EXPECTED_L2:
            fails.append("二层与 215/216 不同构：%s" % l2)

        missing = [r for r in REQUIRED if "%s/%s" % (ROOT_NAME, r) not in names]
        if missing:
            fails.append("缺关键件：%s" % missing)

        trials = sorted({n.split("/")[2] for n in names
                         if n.startswith(ROOT_NAME + "/jobs/") and len(n.split("/")) > 3})
        if len(trials) != 14:
            fails.append("jobs trial 数不是 14：%d %s" % (len(trials), trials))
        for t in trials:
            for need in ("config.json", "result.json"):
                if "%s/jobs/%s/%s" % (ROOT_NAME, t, need) not in names:
                    fails.append("trial %s 缺 %s" % (t, need))
            if not any(n.startswith("%s/jobs/%s/verifier/" % (ROOT_NAME, t)) for n in names):
                fails.append("trial %s 缺 verifier/" % t)
        n_task = sum(1 for t in trials if t.startswith("task__"))
        n_ctl = sum(1 for t in trials if t.startswith("task0__"))
        if (n_task, n_ctl) != (8, 6):
            warns.append("trial 前缀分布不是 8 模型 / 6 控制：%d / %d" % (n_task, n_ctl))

        cfg = json.loads(zf.read("%s/jobs/config.json" % ROOT_NAME).decode("utf-8"))
        scores = {t["trial_name"]: t["score"] for t in cfg["trials"]}
        model_scores = [v for k, v in scores.items() if k.startswith("task__")]
        ctl_scores = [v for k, v in scores.items() if k.startswith("task0__")]
        print("jobs       : n_trials=%s archive_only=%s schema=%s"
              % (cfg.get("n_trials"), cfg.get("archive_only"), cfg.get("schema")))
        print("model scores: %s" % model_scores)
        print("ctl   scores: %s" % ctl_scores)
        if sum(1 for s in model_scores if s == 1) != 1:
            warns.append("模型轮得分分布异常：%s" % model_scores)
        if sum(1 for s in ctl_scores if s == 1) != 3 or ctl_scores.count(0) != 3:
            fails.append("控制轮不是 golden 3x1 + nop 3x0：%s" % ctl_scores)

        tot = sum(i.file_size for i in zf.infolist())
        print("entries    : %d   raw=%.1f MiB" % (len(names), tot / 1048576))

    for w in warns:
        print("[WARN] %s" % w)
    for f in fails:
        print("[FAIL] %s" % f)
    print("\n结果：%s" % ("PASS" if not fails else "FAIL"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
