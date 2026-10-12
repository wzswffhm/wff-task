# -*- coding: utf-8 -*-
"""同步 oracle 原生 output 与两份金标；修正历史阶段遗留的错挂/陈旧文件。"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = REPO / "harbor-weakness" / "FIN3-WKN-150"
BATCH = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix7-150" / "FIN3-WKN-150"
ORACLE_OUT = BATCH / "跑分产物与轨迹" / "oracle" / "output"
GOLDEN_MEMO = TASK / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
GOLDEN_SCRIPT = TASK / "solution" / "golden_output" / "FIN3-WKN-150_reproduce.py"
APPLY = "--apply" in sys.argv


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    targets = {
        "oracle memo": ORACLE_OUT / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        "oracle script": ORACLE_OUT / "FIN3-WKN-150_reproduce.py",
        "golden memo": GOLDEN_MEMO,
        "tests memo": TASK / "tests" / "__golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        "golden script": GOLDEN_SCRIPT,
        "tests script": TASK / "tests" / "__golden_output" / "FIN3-WKN-150_reproduce.py",
    }
    for label, path in targets.items():
        print(f"{label:14} exists={path.is_file()} size={path.stat().st_size if path.exists() else '-'} "
              f"sha={sha(path)[:12] if path.exists() else '-'}")
    print("golden memo revised:", "退出回报测算与信息边界" in GOLDEN_MEMO.read_text(encoding="utf-8"))
    oracle_memo = targets["oracle memo"].read_text(encoding="utf-8")
    print("oracle memo revised:", "退出回报测算与信息边界" in oracle_memo)
    if not APPLY:
        print("DRY RUN")
        return 0
    shutil.copy2(GOLDEN_MEMO, targets["oracle memo"])
    shutil.copy2(GOLDEN_SCRIPT, targets["oracle script"])
    print("copied golden -> oracle output")
    print("oracle memo sha now:", sha(targets["oracle memo"])[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
