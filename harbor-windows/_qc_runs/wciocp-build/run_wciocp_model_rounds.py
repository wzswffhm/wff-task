# -*- coding: utf-8 -*-
"""run_wciocp_model_rounds.py —— 用自定义 Harbor agent 跑 wfflab__wciocp-220 的模型轮次。

轮次固定为 Qwen x3 与 Opus x3（甲方口径：只跑这两个模型；GLM/Kimi 不参与判分）。
每轮一个 Harbor 原生 job，写到题包**外**的 jobs-dir，避免 task checksum 被 jobs 污染。

端点来源：仓库根 models.local.json 的 active 条目（qwen3.8-max、opus-5）。

用法：
    python run_wciocp_model_rounds.py [--only qwen] [--max-steps 40] [--dry-run]
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
PKG = ROOT / "harbor-windows" / "wfflab__wciocp-220-v1.0.0-delivery"
AGENT_DIR = ROOT / "harbor-windows" / "_qc_runs" / "wciocp-build" / "harbor_agent"
STAGE = ROOT / "harbor-windows" / "_qc_runs" / "wciocp-build" / "model-rounds"
HARBOR = Path(os.environ.get(
    "HARBOR_EXE",
    r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe"))
MODELS_LOCAL = ROOT / "models.local.json"
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"

AGENT = "wciocp_model_agent:WindowsCodingModelAgent"

# (alias, 端点 key, 轮数)
ROUNDS = [("qwen", "qwen3.8-max", 3), ("opus", "opus-5", 3)]


def endpoints() -> dict:
    ml = json.loads(MODELS_LOCAL.read_text(encoding="utf-8"))
    by_key = {e.get("key"): e for e in ml["endpoints"]}
    out = {}
    q = by_key["qwen3.8-max"]
    out["qwen"] = {"base_url": q["base_url"], "model": q["model"], "auth": q["auth"],
                   "key": q["api_key"], "max_tokens": int(q["max_tokens"]),
                   "timeout": 900,
                   "extra_body": json.dumps(q.get("extra_body") or {}) or None}
    o = by_key["opus-5"]
    out["opus"] = {"base_url": o["base_url"],
                   # Harbor's model gate maps the model name onto an alias, and
                   # only the names listed in its ALIASES table are recognised;
                   # this endpoint serves the opus alias as claude-opus-5.
                   "model": os.environ.get("wciocp_OPUS_MODEL", "claude-opus-5"),
                   "auth": o["auth"],
                   "key": o["api_key"], "max_tokens": int(os.environ.get("wciocp_OPUS_MAX_TOKENS", o["max_tokens"])),
                   "timeout": 1800, "extra_body": None}
    return out


def run_round(alias: str, ep: dict, index: int, max_steps: int, log) -> dict:
    job_name = "model-%s-%d" % (alias, index)
    key_env_name = "WFF_%s_KEY" % alias.upper()
    env = dict(os.environ)
    env[key_env_name] = ep["key"]
    # Harbor's model agent posts with urllib, which on Windows picks up the
    # registry proxy (HKCU\...\Internet Settings\ProxyServer=127.0.0.1:7897) even
    # while ProxyEnable is 0. That proxy forwards to an upstream pool whose
    # credentials are disabled, so every Opus round came back as an HTTP 502 and
    # was recorded as INVALID. Direct access answers 200 with the same key.
    env["no_proxy"] = "*"
    env["NO_PROXY"] = "*"
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
    STAGE.mkdir(parents=True, exist_ok=True)
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
        % (alias, index, p.returncode, reward, (checksum or "-")[:12], dt))
    return {"alias": alias, "index": index, "job": job_name, "trial": trial,
            "exit": p.returncode, "reward": reward, "checksum": checksum, "elapsed": dt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑某个 alias（逗号分隔）")
    ap.add_argument("--index", help="只跑指定轮次编号（逗号分隔），补跑无效槽位时用，例如 --only opus --index 3")
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
    want_index = {int(s) for s in a.index.split(",")} if a.index else None
    plan = [(al, i) for al, _, n in ROUNDS if not want or al in want
            for i in range(1, n + 1)
            if want_index is None or i in want_index]
    log("plan: %s  max_steps=%d" % (plan, a.max_steps))
    if a.dry_run:
        for al, i in plan:
            ep = eps[al]
            log("  dry-run %s #%d model=%s base=%s auth=%s key_len=%d"
                % (al, i, ep["model"], ep["base_url"], ep["auth"], len(ep["key"])))
        return 0

    summary_path = STAGE / "rounds_summary.json"
    existing = []
    if summary_path.is_file():
        try:
            existing = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        except Exception:
            existing = []

    results = []
    for al, i in plan:
        log("=== %s #%d 开跑 ===" % (al, i))
        results.append(run_round(al, eps[al], i, a.max_steps, log))

    # A replacement round belongs to the slot it re-runs: replace that slot and
    # keep every other recorded round untouched.
    merged = [r for r in existing if not any(
        r.get("alias") == n.get("alias") and r.get("index") == n.get("index") for n in results)]
    merged.extend(results)
    merged.sort(key=lambda r: (str(r.get("alias")), int(r.get("index") or 0)))
    summary_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = [r for r in results if r["reward"] in ("0", "1")]
    log("完成：%d/%d 轮有正式分（汇总现含 %d 轮）" % (len(ok), len(results), len(merged)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
