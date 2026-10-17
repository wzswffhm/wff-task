# -*- coding: utf-8 -*-
"""run_wsparse_controls.py —— wfflab__wsparse-215 的 Golden / no-change 六轮 Harbor 原生对照。

  * ctl-oracle-N：Harbor 内置 oracle agent（把 solution/ 送进容器执行）→ 期望 1
  * ctl-nop-N   ：Harbor 内置 nop agent（no-change）                  → 期望 0

每轮一个 Harbor 原生 job，写到题包**外**的 jobs-dir，避免 task checksum 被 jobs 污染。

用法：
    python run_wsparse_controls.py [--rounds 3] [--only oracle] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wsparse-215-v1.0.1-delivery"
STAGE = ROOT / "harbor-windows" / "_qc_runs" / "wsparse-build" / "controls"
HARBOR = Path(os.environ.get(
    "HARBOR_EXE",
    r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe"))
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"

ROLES = ("oracle", "nop")


def run_case(role: str, index: int, log) -> dict:
    job_name = "ctl-%s-%d" % (role, index)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PATH"] = DOCKER_BIN + os.pathsep + env.get("PATH", "")
    cmd = [str(HARBOR), "run", "--path", str(PKG), "--agent", role,
           "-k", "1", "-n", "1", "-r", "0",
           "--jobs-dir", str(STAGE / "jobs"), "--job-name", job_name,
           "--quiet", "--yes"]
    STAGE.mkdir(parents=True, exist_ok=True)
    jlog = STAGE / ("%s.log" % job_name)
    t0 = time.time()
    with jlog.open("w", encoding="utf-8", errors="replace") as fh:
        p = subprocess.run(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT)
    dt = int(time.time() - t0)

    job_dir = STAGE / "jobs" / job_name
    reward = None
    checksum = None
    trial = None
    if job_dir.is_dir():
        for d in sorted(job_dir.iterdir()):
            if d.is_dir() and "__" in d.name:
                trial = d.name
                rp = d / "verifier" / "reward.txt"
                if rp.is_file():
                    reward = rp.read_text(encoding="utf-8-sig").strip()
                rj = d / "result.json"
                if rj.is_file():
                    try:
                        checksum = json.loads(
                            rj.read_text(encoding="utf-8-sig")).get("task_checksum")
                    except Exception:
                        pass
    log("  %-6s #%d exit=%s reward=%s checksum=%s elapsed=%ss"
        % (role, index, p.returncode, reward, (checksum or "-")[:12], dt))
    return {"role": role, "index": index, "job": job_name, "trial": trial,
            "exit": p.returncode, "reward": reward, "checksum": checksum, "elapsed": dt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--only", help="只跑 oracle 或 nop")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    STAGE.mkdir(parents=True, exist_ok=True)
    logfile = STAGE / "controls.log"
    fh = logfile.open("a", encoding="utf-8")

    def log(msg):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()

    if (PKG / "jobs").exists():
        log("!! 题包里存在 jobs/，会导致 task checksum 与自检期望不一致；请先移走。")
        return 2

    roles = [a.only] if a.only else list(ROLES)
    if a.dry_run:
        log("dry-run: %s" % [(r, i) for r in roles for i in range(1, a.rounds + 1)])
        return 0

    results = []
    for role in roles:
        for i in range(1, a.rounds + 1):
            log("=== ctl-%s-%d 开跑 ===" % (role, i))
            results.append(run_case(role, i, log))
    (STAGE / "controls_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    expected = {"oracle": "1", "nop": "0"}
    ok = [r for r in results if r["reward"] == expected.get(r["role"])]
    log("完成：%d/%d 轮符合预期" % (len(ok), len(results)))
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
