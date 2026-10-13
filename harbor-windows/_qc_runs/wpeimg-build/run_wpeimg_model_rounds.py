# -*- coding: utf-8 -*-
"""run_wpeimg_model_rounds.py —— 用自定义 Harbor agent 跑 218 的 8 轮模型（容器内）。

轮次固定：Qwen x3、Opus x3、GLM x1、Kimi x1（与新版自检的 REQUIRED_COUNTS 一致）。
每轮一个 Harbor 原生 job（写到题包**外**的 jobs-dir，保证 task checksum 不被 jobs 污染）。

端点来源：
  * qwen / glm / kimi —— 仓库根 models.local.json 的 active 条目
  * opus —— deliverables/2026-10-04_outside-harbor-win/runner/.env.local（4router.net）

用法：
    python run_wpeimg_model_rounds.py [--only opus] [--max-steps 40] [--dry-run]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wpeimg-219-v1.0.0-delivery"
AGENT_DIR = ROOT / "harbor-windows" / "_qc_runs" / "wpeimg-build" / "harbor_agent"
STAGE = ROOT / "harbor-windows" / "_qc_runs" / "wpeimg-build" / "model-rounds"
HARBOR = Path(os.environ.get("HARBOR_EXE",
                             r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe"))
ENV_LOCAL = ROOT / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / ".env.local"
MODELS_LOCAL = ROOT / "models.local.json"
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"

AGENT = "wpeimg_model_agent:WindowsCodingModelAgent"

# (alias, key_env, rounds)
ROUNDS = [("qwen", "QWEN_API_KEY", 3), ("opus", "OPUS_API_KEY", 3),
          ("glm", "GLM_API_KEY", 1), ("kimi", "KIMI_API_KEY", 1)]


def parse_env_file(path: Path) -> dict:
    vals = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def endpoints() -> dict:
    ml = json.loads(MODELS_LOCAL.read_text(encoding="utf-8"))
    eps = {e.get("key"): e for e in ml["endpoints"]}
    env = parse_env_file(ENV_LOCAL)
    out = {}
    q = eps["qwen3.8-max"]
    out["qwen"] = {"base_url": q["base_url"], "model": q["model"], "auth": "x-api-key",
                   "key": q["api_key"], "max_tokens": 65536, "timeout": 900,
                   "extra_body": json.dumps({"thinking": {"type": "disabled"}})}
    g = eps["glm-5.3"]
    out["glm"] = {"base_url": g["base_url"], "model": g["model"], "auth": "authorization",
                  "key": g["api_key"], "max_tokens": 65536, "timeout": 1200,
                  "extra_body": None}
    k = eps["kimi-k3"]
    out["kimi"] = {"base_url": k["base_url"], "model": k["model"], "auth": "authorization",
                   "key": k["api_key"], "max_tokens": 32000, "timeout": 900,
                   "extra_body": json.dumps({"thinking": {"type": "disabled"}})}
    out["opus"] = {"base_url": env.get("OPUS_BASE_URL", "https://4router.net"),
                   "model": env.get("OPUS_MODEL", "claude-opus-5"), "auth": "x-api-key",
                   "key": env["OPUS_API_KEY"], "max_tokens": 32000,
                   "timeout": int(env.get("OPUS_REQUEST_TIMEOUT", 1800)),
                   "extra_body": None}
    return out


def run_round(alias: str, ep: dict, index: int, max_steps: int, log) -> dict:
    job_name = "model-%s-%d" % (alias, index)
    key_env_name = "WFF_%s_KEY" % alias.upper()
    env = dict(os.environ)
    env[key_env_name] = ep["key"]
    env["PYTHONPATH"] = str(AGENT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PATH"] = DOCKER_BIN + os.pathsep + env.get("PATH", "")
    cmd = [str(HARBOR), "run", "--path", str(PKG), "--agent", AGENT,
           "--model", ep["model"],
           "--ak", "alias=" + alias,
           "--ak", "base_url=" + ep["base_url"],
           "--ak", "auth=" + ep["auth"],
           "--ak", "api_key_env=" + key_env_name,
           "--ak", "max_tokens=%d" % ep["max_tokens"],
           "--ak", "request_timeout=%d" % ep["timeout"],
           "--ak", "max_steps=%d" % max_steps]
    if ep.get("extra_body"):
        cmd += ["--ak", "extra_body=" + ep["extra_body"]]
    cmd += ["-k", "1", "-n", "1", "-r", "0",
            "--jobs-dir", str(STAGE / "jobs"), "--job-name", job_name, "--quiet", "--yes"]
    t0 = time.time()
    jlog = STAGE / ("%s.log" % job_name)
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
                        checksum = json.loads(rj.read_text(encoding="utf-8-sig")).get("task_checksum")
                    except Exception:
                        pass
    log("  %-6s #%d exit=%s reward=%s checksum=%s elapsed=%ss"
        % (alias, index, p.returncode, reward, (checksum or "-")[:12], dt))
    return {"alias": alias, "index": index, "job": job_name, "trial": trial,
            "exit": p.returncode, "reward": reward, "checksum": checksum, "elapsed": dt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑某个 alias（逗号分隔）")
    ap.add_argument("--max-steps", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    STAGE.mkdir(parents=True, exist_ok=True)
    logfile = STAGE / "rounds.log"
    fh = logfile.open("a", encoding="utf-8")

    def log(msg):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()

    if (PKG / "jobs").exists():
        log("!! 题包里存在 jobs/，会导致 task checksum 与自检期望不一致；请先移走。")
        return 2

    eps = endpoints()
    want = [s.strip() for s in a.only.split(",")] if a.only else None
    plan = [(al, i) for al, _, n in ROUNDS if not want or al in want
            for i in range(1, n + 1)]
    log("plan: %s  max_steps=%d" % (plan, a.max_steps))
    if a.dry_run:
        for al, i in plan:
            ep = eps[al]
            log("  dry-run %s #%d model=%s base=%s auth=%s key_len=%d"
                % (al, i, ep["model"], ep["base_url"], ep["auth"], len(ep["key"])))
        return 0

    results = []
    for al, i in plan:
        log("=== %s #%d 开跑 ===" % (al, i))
        results.append(run_round(al, eps[al], i, a.max_steps, log))
    (STAGE / "rounds_summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in results if r["reward"] in ("0", "1")]
    log("完成：%d/%d 轮有正式分" % (len(ok), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
