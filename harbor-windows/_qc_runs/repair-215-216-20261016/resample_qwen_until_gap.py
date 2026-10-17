# -*- coding: utf-8 -*-
"""重采样 Qwen 轮，直到某一组 3 轮里出现非满分，然后重建包内 jobs/。

用户指令：不改题包，重跑 qwen，直到 3 次（一轮组的 3 次运行）不是全满分；
旧的跑分记录清理掉（每次重采样覆盖同名 job，交付包里只保留最终一组）。

用法：
    python resample_qwen_until_gap.py [--max-attempts 20] [--only wsparse|wvas]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = ROOT / "harbor-windows"
PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
HARBOR_SCRIPTS = r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts"
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
LOGDIR = HW / "_qc_runs" / "repair-215-216-20261016"

PACKAGES = [
    ("wsparse-build", "wsparse", "wfflab__wsparse-215-v1.0.1-delivery"),
    ("wvas-build", "wvas", "wfflab__wvas-216-v1.0.1-delivery"),
]


def log(msg: str) -> None:
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with (LOGDIR / "resample.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = HARBOR_SCRIPTS + os.pathsep + DOCKER_BIN + os.pathsep + e.get("PATH", "")
    e["no_proxy"] = "*"
    e["NO_PROXY"] = "*"
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    return e


def rewards(stage: Path) -> list[tuple[str, str]]:
    out = []
    jobs = stage / "jobs"
    if not jobs.is_dir():
        return out
    for job in sorted(p for p in jobs.iterdir() if p.is_dir()):
        for trial in job.iterdir():
            rp = trial / "verifier" / "reward.txt"
            if rp.is_file():
                out.append((job.name, rp.read_text(encoding="utf-8-sig").strip()))
                break
    return out


def run(build: Path, script: str, args: list[str], tag: str) -> int:
    logfile = LOGDIR / ("%s-%s-%s.out" % (build.name, script.replace(".py", ""), tag))
    with logfile.open("a", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run([PY, str(build / script), *args], cwd=str(build),
                           env=env(), stdout=fh, stderr=subprocess.STDOUT)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-attempts", type=int, default=20)
    ap.add_argument("--only")
    a = ap.parse_args()
    LOGDIR.mkdir(parents=True, exist_ok=True)

    for build_name, mod, pkg_name in PACKAGES:
        if a.only and a.only not in (mod, build_name):
            continue
        build = HW / "_qc_runs" / build_name
        pkg = HW / pkg_name
        stage = build / "model-rounds"
        log("=" * 70)
        log("### %s 开始 Qwen 重采样" % pkg_name)

        # model-rounds 脚本要求包内没有 jobs/；把现有一份归档（旧跑分记录清理）
        if (pkg / "jobs").exists():
            dest = build / "jobs-before-qwen-resample"
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(pkg / "jobs"), str(dest))
            log("  已归档旧 jobs/ -> %s" % dest.name)

        ok = False
        for attempt in range(1, a.max_attempts + 1):
            log("--- %s 第 %d 次尝试：重跑 Qwen x3" % (pkg_name, attempt))
            # 清掉上一次尝试的 Qwen job 目录，保证交付包里只有最终一组
            qwen_jobs = stage / "jobs"
            if qwen_jobs.is_dir():
                for d in list(qwen_jobs.iterdir()):
                    if d.is_dir() and d.name.startswith("model-qwen"):
                        shutil.rmtree(d, ignore_errors=True)
            rc = run(build, "run_%s_model_rounds.py" % mod,
                     ["--only", "qwen", "--max-steps", "40"], "attempt%02d" % attempt)
            rs = [(n, r) for n, r in rewards(stage) if n.startswith("model-qwen")]
            log("  第 %d 次结果：%s (exit=%s)" % (attempt, rs, rc))
            if len(rs) == 3 and any(r != "1" for _n, r in rs):
                log("  满足条件：3 轮中出现非满分")
                ok = True
                break
            log("  3 轮全满分，继续重采样")
        if not ok:
            log("!! 达到最大尝试次数仍全满分：%s" % pkg_name)
            return 1

        rc = run(build, "assemble_%s_harbor_jobs.py" % mod, [], "assemble-final")
        log("### %s 组装完成 exit=%s" % (pkg_name, rc))
        if rc != 0:
            return rc
    log("Qwen 重采样全部结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
