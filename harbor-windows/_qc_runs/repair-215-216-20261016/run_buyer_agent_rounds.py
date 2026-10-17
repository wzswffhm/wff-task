# -*- coding: utf-8 -*-
"""按甲方配置（windows-claude-code agent + relay）跑 215/216 的模型轮。

调用链（与甲方 README 一致）：
  harbor run -p <task> -a agent.windows_claude_code:WindowsClaudeCodeAgent
    -m <model> --no-force-build --n-concurrent 1 --jobs-dir <dir> --delete -y --quiet
  容器内 C:\\node\\claude.cmd -> http://host.docker.internal:<relay> -> 上游

前置：两个 relay 已启动（qwen 18184 / claude 18183），镜像里已有 C:\\node\\claude.cmd。

用法：
  python run_buyer_agent_rounds.py --pkg wsparse --rounds 4
  python run_buyer_agent_rounds.py --pkg wvas --model qwen --rounds 4
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
HW = ROOT / "harbor-windows"
HARBOR = Path(r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe")
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
LOGDIR = HW / "_qc_runs" / "repair-215-216-20261016"

PACKAGES = {
    "wsparse": ("wfflab__wsparse-215-v1.0.1-delivery", HW / "_qc_runs" / "wsparse-build" / "buyer-agent-jobs"),
    "wvas": ("wfflab__wvas-216-v1.0.1-delivery", HW / "_qc_runs" / "wvas-build" / "buyer-agent-jobs"),
}
MODELS = {
    "qwen": ("qwen3.8-max-0902", 18184, "qwen_3_8_max"),
    "opus": ("claude-opus-5", 18183, "claude_opus_5"),
}


def log(msg: str) -> None:
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with (LOGDIR / "buyer-agent.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


PSD1 = ROOT / ".local" / "harbor-models.psd1"


def load_profiles() -> dict:
    """Parse .local/harbor-models.psd1 without PowerShell.

    The sandbox runs Windows PowerShell in ConstrainedLanguage mode, where
    Import-PowerShellDataFile is unavailable, so the small data file is parsed
    directly. Its shape is fixed by the buyer's example template.
    """
    import re

    text = PSD1.read_text(encoding="utf-8-sig")
    profiles: dict = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        head = re.match(r"(\w+)\s*=\s*@\{", line)
        if head:
            name = head.group(1)
            current = None if name == "Profiles" else name
            if current:
                profiles[current] = {}
            continue
        if current and line == "}":
            current = None
            continue
        if current:
            field = re.match(r"(Model|ApiKey|BaseUrl|Agent)\s*=\s*'([^']*)'", line)
            if field:
                profiles[current][field.group(1)] = field.group(2)
    if not profiles:
        raise RuntimeError("no profiles parsed from %s" % PSD1)
    return profiles


def env_for(profile: dict, relay_port: int) -> dict:
    e = dict(os.environ)
    e["PATH"] = DOCKER_BIN + os.pathsep + e.get("PATH", "")
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e["WINDOWS_CLAUDE_API_KEY"] = str(profile["ApiKey"])
    e["WINDOWS_CLAUDE_BASE_URL"] = "http://host.docker.internal:%d" % relay_port
    e["WINDOWS_CLAUDE_MODEL"] = str(profile["Model"])
    return e


def reward_of(job_dir: Path) -> tuple[str, str]:
    for trial in job_dir.iterdir() if job_dir.is_dir() else []:
        rp = trial / "verifier" / "reward.txt"
        if rp.is_file():
            return rp.read_text(encoding="utf-8-sig").strip(), trial.name
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True, choices=sorted(PACKAGES))
    ap.add_argument("--model", choices=sorted(MODELS))
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--max-steps", type=int, default=0, help="0 = 用 agent 默认")
    a = ap.parse_args()
    LOGDIR.mkdir(parents=True, exist_ok=True)

    pkg_name, jobs_dir = PACKAGES[a.pkg]
    task_path = HW / pkg_name
    jobs_dir.mkdir(parents=True, exist_ok=True)
    profiles = load_profiles()
    aliases = [a.model] if a.model else ["qwen", "opus"]

    summary = []
    for alias in aliases:
        model, port, profile_name = MODELS[alias]
        profile = profiles[profile_name]
        env = env_for(profile, port)
        for i in range(1, a.rounds + 1):
            job_name = "%s-%s-%d" % (a.pkg, alias, i)
            cmd = [str(HARBOR), "run", "-p", str(task_path),
                   "-a", "agent.windows_claude_code:WindowsClaudeCodeAgent",
                   "-m", model, "--no-force-build", "--n-concurrent", "1",
                   "--jobs-dir", str(jobs_dir), "--delete", "-y", "--quiet",
                   "--job-name", job_name]
            logfile = LOGDIR / ("buyer-%s.log" % job_name)
            log(">>> %s model=%s relay=%d" % (job_name, model, port))
            t0 = time.time()
            with logfile.open("w", encoding="utf-8", errors="replace") as fh:
                proc = subprocess.run(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT)
            reward, trial = reward_of(jobs_dir / job_name)
            dt = int(time.time() - t0)
            log("<<< %s exit=%s reward=%s elapsed=%ss" % (job_name, proc.returncode, reward or "-", dt))
            summary.append({"job": job_name, "package": pkg_name, "alias": alias,
                            "model": model, "exit": proc.returncode, "reward": reward,
                            "trial": trial, "elapsed": dt})
    out = LOGDIR / ("buyer-summary-%s.json" % a.pkg)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    log("written %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
