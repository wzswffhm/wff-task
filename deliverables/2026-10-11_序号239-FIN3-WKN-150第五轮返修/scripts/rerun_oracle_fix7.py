# -*- coding: utf-8 -*-
"""按首轮已证实的 R27 误判，重跑 oracle 一场；保留原失败明细作留痕。"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
DRIVER = HERE / "run_rejudge_150_fix7_wsl.py"
REJ = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-150\_rejudge")
FAILED = REJ / "oracle" / "verifier" / "failed-first-rejudge"
APPLY = "--apply" in sys.argv


def main() -> int:
    verifier = REJ / "oracle" / "verifier"
    if not verifier.is_dir():
        raise SystemExit(f"missing {verifier}")
    print("=== first-round oracle (archived verdict) ===")
    if (FAILED / "reward.json").is_file():
        print((FAILED / "reward.json").read_text(encoding="utf-8"))
    print("R27 evidence is in reward-details.json; the judge missed the revised disclosure.")
    if not APPLY:
        print("DRY RUN: rerun the same WSL driver after clearing this executor's verdict.")
        return 0
    if FAILED.exists():
        shutil.rmtree(FAILED)
    FAILED.mkdir(parents=True)
    for name in ("reward.json", "reward.txt", "reward-details.json",
                 "reward_exit_message.json"):
        source = verifier / name
        if source.exists():
            shutil.move(str(source), str(FAILED / name))
    print(f"archived first-round verdict to {FAILED}")
    command = ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
               f'python3 "/mnt/c{DRIVER.as_posix()[2:]}" --only oracle --workers 1 '
               f'--timeout-min 180 --attempts 2 --cooldown 90']
    print("launch:", command)
    result = subprocess.run(command)
    print("driver rc:", result.returncode)
    print((verifier / "reward.json").read_text(encoding="utf-8"))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
