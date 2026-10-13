# -*- coding: utf-8 -*-
"""rerun_slot.py -- 按「绑定同一计划槽位」规则重跑一个模型轮次。

用法：
    python rerun_slot.py --task 219 --alias opus --index 3 --job-name model-opus-3-rerun

行为：
  * 直接调用 harbor run，与 driver.py 的 models 阶段完全同参（同 alias / 同模型 /
    同 base_url / 同 max_steps），只是 job 名不同 —— 目的是保留原失败试次，同时
    用新试次替代它的计划槽位；
  * 结果写到 <run>/<task>/replacement-rounds/jobs/<job-name>/。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import driver as D  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(D.TASKS))
    ap.add_argument("--alias", required=True)
    ap.add_argument("--index", type=int, required=True)
    ap.add_argument("--job-name", default="")
    ap.add_argument("--max-steps", type=int, default=40)
    a = ap.parse_args()

    cfg = D.TASKS[a.task]
    pkg = D.STAGED / cfg["pkg_name"]
    out = D.REL / (a.task + os.environ.get("WFF_RUN_SUFFIX", ""))
    jobs = out / "replacement-rounds" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    job_name = a.job_name or ("model-%s-%d-rerun" % (a.alias, a.index))
    logfile = out / "driver.log"

    if (pkg / "jobs").exists() and (pkg / "jobs").is_dir():
        # during the run window the package must not carry jobs/ (dirhash contract)
        pass

    eps = D.endpoints()
    ep = eps[a.alias]
    key_env = "WFF_%s_KEY" % a.alias.upper()
    extra_env = {key_env: ep["key"], "PYTHONPATH": str(cfg["agent_dir"])}
    cmd = [str(D.HARBOR), "run", "--path", str(pkg), "--agent", cfg["agent"],
           "--model", ep["model"],
           "--ak", "alias=" + a.alias,
           "--ak", "base_url=" + ep["base_url"],
           "--ak", "auth=" + ep["auth"],
           "--ak", "api_key_env=" + key_env,
           "--ak", "max_tokens=%d" % ep["max_tokens"],
           "--ak", "request_timeout=%d" % ep["timeout"],
           "--ak", "max_steps=%d" % a.max_steps]
    if ep.get("extra_body"):
        cmd += ["--ak", "extra_body=" + ep["extra_body"]]
    cmd += ["--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
            "--jobs-dir", str(jobs), "--job-name", job_name, "--quiet", "--yes"]

    D.log(logfile, "=== 替代轮 %s（alias=%s #%d, model=%s）==="
          % (job_name, a.alias, a.index, ep["model"]))
    t0 = time.time()
    with (out / "replacement-rounds" / ("%s.log" % job_name)).open(
            "w", encoding="utf-8", errors="replace") as fh:
        p = subprocess.run(cmd, env=D.harbor_env(extra_env), stdout=fh, stderr=subprocess.STDOUT)
    dt = int(time.time() - t0)
    info = D.read_trial(jobs / job_name)
    D.log(logfile, "  %-22s exit=%s reward=%s checksum=%s elapsed=%ss"
          % (job_name, p.returncode, info["reward"], (info["checksum"] or "-")[:12], dt))
    (out / "replacement-rounds" / "summary.json").write_text(
        json.dumps({"alias": a.alias, "index": a.index, "job": job_name,
                    "exit": p.returncode, "elapsed": dt, **info},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
