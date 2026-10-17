# -*- coding: utf-8 -*-
"""整改后重跑 215 / 216 的 12 组 job。

顺序（每包）：
  1. run_<mod>_controls.py  --rounds 3     → Oracle x3 + NOP x3
  2. run_<mod>_model_rounds.py --max-steps 40 → Qwen x3 + Opus x3
  3. assemble_<mod>_harbor_jobs.py         → 组装进 <pkg>/jobs

前置：两包的 jobs/ 与 build 下的 controls/、model-rounds/ 已归档到
      *_old-repair-20261016，controls 脚本要求 PKG/jobs 不存在。
"""
from __future__ import annotations

import os
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
    with (LOGDIR / "rerun.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = HARBOR_SCRIPTS + os.pathsep + DOCKER_BIN + os.pathsep + e.get("PATH", "")
    e["no_proxy"] = "*"
    e["NO_PROXY"] = "*"
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    return e


def run(build: Path, script: str, args: list[str], label: str) -> int:
    log(">>> %s" % label)
    if not (build / script).is_file():
        log("!! 缺脚本 %s" % (build / script))
        return 127
    logfile = LOGDIR / ("%s-%s.out" % (build.name, script.replace(".py", "")))
    with logfile.open("a", encoding="utf-8", errors="replace") as fh:
        r = subprocess.run([PY, str(build / script), *args], cwd=str(build),
                           env=env(), stdout=fh, stderr=subprocess.STDOUT)
    log("<<< %s exit=%s (log %s)" % (label, r.returncode, logfile.name))
    return r.returncode


def main() -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    rc_all = 0
    for build_name, mod, pkg_name in PACKAGES:
        build = HW / "_qc_runs" / build_name
        pkg = HW / pkg_name
        log("=" * 70)
        log("### %s (%s)" % (pkg_name, build_name))
        if (pkg / "jobs").exists():
            log("!! %s/jobs 仍存在，controls 会拒绝运行" % pkg_name)
            rc_all = 1
            continue
        rc1 = run(build, "run_%s_controls.py" % mod, ["--rounds", "3"], "%s 控制组 6 轮" % pkg_name)
        rc2 = run(build, "run_%s_model_rounds.py" % mod, ["--max-steps", "40"], "%s 模型轮 6 轮" % pkg_name)
        rc3 = run(build, "assemble_%s_harbor_jobs.py" % mod, [], "%s 组装 jobs/" % pkg_name)
        for rc in (rc1, rc2, rc3):
            if rc != 0:
                rc_all = 1
        log("### %s 完成: controls=%s model=%s assemble=%s" % (pkg_name, rc1, rc2, rc3))
    log("全部重跑结束 rc=%s" % rc_all)
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
