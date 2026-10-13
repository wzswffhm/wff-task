# -*- coding: utf-8 -*-
"""driver.py —— 218/219 v1.1.0 的跑分编排（打包 / 控制组 / 模型轮次 / 组装 jobs）。

用法：
    python driver.py --task 218 --stage package
    python driver.py --task 219 --stage dry-run
    python driver.py --task 218 --stage controls
    python driver.py --task 218 --stage models [--only qwen,opus] [--max-steps 40]

约定：
  * 题包目录：harbor-windows/_qc_runs/relaunch-20261013/staged/<pkg>（跑分期间不含 jobs/）
  * 控制组产物：_qc_runs/relaunch-20261013/<task>/controls/jobs/<job-name>/
  * 模型轮次产物：_qc_runs/relaunch-20261013/<task>/model-rounds/jobs/<job-name>/
  * 交付 zip：deliverables/2026-10-13_<task>-v1.1.0-交付/package/<pkg>.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"
STAGED = REL / "staged"
HARBOR = Path(os.environ.get(
    "HARBOR_EXE", r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe"))
MODELS_LOCAL = ROOT / "models.local.json"
ENV_LOCAL = ROOT / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / ".env.local"
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"
HARBOR_SCRIPTS = r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts"

TASKS = {
    "218": {
        "pkg_name": "wfflab__wlogseg-218-v1.1.0-delivery",
        "task_id": "wfflab__wlogseg-218",
        "version": "1.1.0",
        "agent_module": "wlogseg_model_agent",
        "agent_dir": ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build" / "harbor_agent",
        "agent": "wlogseg_model_agent:WindowsCodingModelAgent",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wlogseg218-返修",
    },
    "219": {
        "pkg_name": "wfflab__wpeimg-219-v1.4.0-delivery",
        "task_id": "wfflab__wpeimg-219",
        "version": "1.4.0",
        "agent_module": "wpeimg_model_agent",
        "agent_dir": ROOT / "harbor-windows" / "_qc_runs" / "wpeimg-build" / "harbor_agent",
        "agent": "wpeimg_model_agent:WindowsCodingModelAgent",
        "deliverable": ROOT / "deliverables" / "2026-10-13_wpeimg219-返修",
    },
}

# The buyer gate requires exactly 14 Harbor jobs: qwen x3, opus x3, glm x1,
# kimi x1, oracle x3, nop x3. GLM and Kimi do not take part in the
# discrimination rule, but their single rounds are mandatory for the gate.
ROUNDS = [("qwen", 3), ("opus", 3), ("glm", 1), ("kimi", 1)]

STORE_SUFFIXES = {".zip", ".whl", ".png", ".jpg", ".jpeg", ".gz", ".7z", ".exe"}
# jobs/ IS part of the delivery (the buyer gate requires the 14 native Harbor
# jobs inside the task root); only caches are excluded.
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "exception.txt"}


def log(path: Path, msg: str) -> None:
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


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
                   "key": env["OPUS_API_KEY"], "max_tokens": 32000, "timeout": 240,
                   "extra_body": None}
    return out


def harbor_env(extra: dict | None = None) -> dict:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([HARBOR_SCRIPTS, DOCKER_BIN, env.get("PATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONPATH", None)
    if extra:
        env.update(extra)
    return env


def read_trial(job_dir: Path) -> dict:
    info = {"job": job_dir.name, "trial": None, "reward": None, "checksum": None,
            "exit_code": None, "result_json": None}
    if not job_dir.is_dir():
        return info
    for d in sorted(job_dir.iterdir()):
        if d.is_dir() and "__" in d.name:
            info["trial"] = d.name
            rp = d / "verifier" / "reward.txt"
            if rp.is_file():
                info["reward"] = rp.read_text(encoding="utf-8-sig").strip()
            rj = d / "result.json"
            if rj.is_file():
                info["result_json"] = str(rj)
                try:
                    doc = json.loads(rj.read_text(encoding="utf-8-sig"))
                    info["checksum"] = doc.get("task_checksum")
                except Exception:  # noqa: BLE001
                    pass
    return info


# --------------------------------------------------------------------- stages

def stage_inspect(cfg: dict, out: Path) -> int:
    pkg = STAGED / cfg["pkg_name"]
    logfile = out / "driver.log"
    log(logfile, "inspect %s" % pkg)
    if (pkg / "jobs").exists():
        log(logfile, "!! jobs/ 存在，跑分期间必须为空")
        return 2
    total = sum(1 for _ in pkg.rglob("*") if _.is_file())
    log(logfile, "files=%d" % total)
    return 0


def stage_dry_run(cfg: dict, out: Path) -> int:
    logfile = out / "driver.log"
    eps = endpoints()
    for al, n in ROUNDS:
        ep = eps[al]
        log(logfile, "%-5s x%d model=%s base=%s auth=%s key_len=%d max_tokens=%d"
            % (al, n, ep["model"], ep["base_url"], ep["auth"], len(ep["key"]), ep["max_tokens"]))
    pkg = STAGED / cfg["pkg_name"]
    log(logfile, "package=%s exists=%s" % (pkg, pkg.is_dir()))
    log(logfile, "harbor=%s exists=%s" % (HARBOR, HARBOR.is_file()))
    return 0


def stage_build(cfg: dict, out: Path) -> int:
    """构建任务镜像（不跑 agent），确认 Dockerfile 与素材可用。"""
    logfile = out / "driver.log"
    pkg = STAGED / cfg["pkg_name"]
    jobs = out / "build-jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    cmd = [str(HARBOR), "run", "--path", str(pkg), "--agent", "oracle",
           "-k", "1", "-n", "1", "-r", "0",
           "--jobs-dir", str(jobs), "--job-name", "build-probe",
           "--quiet", "--yes"]
    log(logfile, "build: " + " ".join(cmd[:8]) + " ...")
    with (out / "build.log").open("w", encoding="utf-8", errors="replace") as fh:
        p = subprocess.run(cmd, env=harbor_env(), stdout=fh, stderr=subprocess.STDOUT)
    log(logfile, "build exit=%s" % p.returncode)
    return p.returncode


def stage_controls(cfg: dict, out: Path) -> int:
    logfile = out / "driver.log"
    pkg = STAGED / cfg["pkg_name"]
    jobs = out / "controls" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    if (pkg / "jobs").exists():
        log(logfile, "!! jobs/ 存在，跑分期间必须为空")
        return 2
    results = []
    for agent in ("oracle", "nop"):
        for i in range(1, 4):
            name = "ctl-%s-%d" % (agent, i)
            cmd = [str(HARBOR), "run", "--path", str(pkg), "--agent", agent,
                   "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
                   "--jobs-dir", str(jobs), "--job-name", name, "--quiet", "--yes"]
            t0 = time.time()
            log(logfile, "=== %s 开跑 ===" % name)
            with (out / "controls" / ("%s.log" % name)).open(
                    "w", encoding="utf-8", errors="replace") as fh:
                p = subprocess.run(cmd, env=harbor_env(), stdout=fh, stderr=subprocess.STDOUT)
            dt = int(time.time() - t0)
            info = read_trial(jobs / name)
            info["exit"] = p.returncode
            info["elapsed"] = dt
            results.append(info)
            log(logfile, "  %-12s exit=%s reward=%s checksum=%s elapsed=%ss"
                % (name, p.returncode, info["reward"], (info["checksum"] or "-")[:12], dt))
    (out / "controls" / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def stage_models(cfg: dict, out: Path, only: str | None, max_steps: int) -> int:
    logfile = out / "driver.log"
    pkg = STAGED / cfg["pkg_name"]
    jobs = out / "model-rounds" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    if (pkg / "jobs").exists():
        log(logfile, "!! jobs/ 存在，跑分期间必须为空")
        return 2
    eps = endpoints()
    want = [s.strip() for s in only.split(",")] if only else None
    plan = [(al, i) for al, n in ROUNDS if not want or al in want for i in range(1, n + 1)]
    log(logfile, "plan=%s max_steps=%d" % (plan, max_steps))
    results = []
    for al, i in plan:
        ep = eps[al]
        name = "model-%s-%d" % (al, i)
        key_env = "WFF_%s_KEY" % al.upper()
        extra_env = {key_env: ep["key"], "PYTHONPATH": str(cfg["agent_dir"])}
        cmd = [str(HARBOR), "run", "--path", str(pkg), "--agent", cfg["agent"],
               "--model", ep["model"],
               "--ak", "alias=" + al,
               "--ak", "base_url=" + ep["base_url"],
               "--ak", "auth=" + ep["auth"],
               "--ak", "api_key_env=" + key_env,
               "--ak", "max_tokens=%d" % ep["max_tokens"],
               "--ak", "request_timeout=%d" % ep["timeout"],
               "--ak", "max_steps=%d" % max_steps]
        if ep.get("extra_body"):
            cmd += ["--ak", "extra_body=" + ep["extra_body"]]
        cmd += ["--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
                "--jobs-dir", str(jobs), "--job-name", name, "--quiet", "--yes"]
        t0 = time.time()
        log(logfile, "=== %s 开跑（model=%s）===" % (name, ep["model"]))
        with (out / "model-rounds" / ("%s.log" % name)).open(
                "w", encoding="utf-8", errors="replace") as fh:
            p = subprocess.run(cmd, env=harbor_env(extra_env), stdout=fh, stderr=subprocess.STDOUT)
        dt = int(time.time() - t0)
        info = read_trial(jobs / name)
        info["alias"] = al
        info["index"] = i
        info["exit"] = p.returncode
        info["elapsed"] = dt
        results.append(info)
        log(logfile, "  %-14s exit=%s reward=%s checksum=%s elapsed=%ss"
            % (name, p.returncode, info["reward"], (info["checksum"] or "-")[:12], dt))
        (out / "model-rounds" / "rounds_summary.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def stage_package(cfg: dict, out: Path) -> int:
    logfile = out / "driver.log"
    pkg = STAGED / cfg["pkg_name"]
    dest = cfg["deliverable"] / "package"
    dest.mkdir(parents=True, exist_ok=True)

    # --- delivery hygiene gate: never ship stale data ---------------------
    # Only files that name an *older* version are purged; the evidence produced
    # by this round is generated before packaging and must survive.
    version = cfg["version"]
    older = [v for v in ("1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0") if v != version]
    for path in sorted(cfg["deliverable"].rglob("*"), reverse=True):
        if path.is_file() and any(v in path.name for v in older):
            log(logfile, "hygiene: removing stale deliverable file %s"
                % str(path.relative_to(cfg["deliverable"])).replace("\\", "/"))
            path.unlink()
    for path in sorted(cfg["deliverable"].rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()) and path.name != "package":
            path.rmdir()

    # the empty-directory sweep above may have removed package/ itself, so make
    # sure the destination exists again before creating the archive in it
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = dest / (cfg["pkg_name"] + ".zip")
    if zip_path.exists():
        zip_path.unlink()
    old_sha = dest / (zip_path.name + ".sha256")
    if old_sha.exists():
        old_sha.unlink()
    # only the current version's zip may remain in package/
    for other in list(dest.glob("*.zip")) + list(dest.glob("*.zip.sha256")):
        if other.name.startswith(zip_path.name):
            continue
        log(logfile, "hygiene: removing stale deliverable artifact %s" % other.name)
        other.unlink()
    count = 0
    raw = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(pkg.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(pkg)
            if set(rel.parts) & SKIP_DIRS or path.name in SKIP_FILES:
                continue
            method = (zipfile.ZIP_STORED if path.suffix.lower() in STORE_SUFFIXES
                      else zipfile.ZIP_DEFLATED)
            zf.write(path, arcname="%s/%s" % (cfg["pkg_name"], str(rel).replace("\\", "/")),
                     compress_type=method)
            count += 1
            raw += path.stat().st_size
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (dest / (zip_path.name + ".sha256")).write_text(
        "%s  %s\n" % (digest, zip_path.name), encoding="utf-8")
    with zipfile.ZipFile(zip_path) as zf:
        tops = sorted({n.split("/")[0] for n in zf.namelist()})
    report = {"zip": str(zip_path), "entries": count, "raw_bytes": raw,
              "zip_bytes": zip_path.stat().st_size, "sha256": digest, "tops": tops}
    log(logfile, json.dumps(report, ensure_ascii=False))
    if tops != [cfg["pkg_name"]]:
        log(logfile, "!! zip 顶层不是单一同名目录：%s" % tops)
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--stage", required=True,
                    choices=["inspect", "dry-run", "build", "controls", "models", "package"])
    ap.add_argument("--only", default="")
    ap.add_argument("--max-steps", type=int, default=40)
    a = ap.parse_args()

    cfg = TASKS[a.task]
    out = REL / (a.task + os.environ.get("WFF_RUN_SUFFIX", ""))
    out.mkdir(parents=True, exist_ok=True)
    if a.stage == "inspect":
        return stage_inspect(cfg, out)
    if a.stage == "dry-run":
        return stage_dry_run(cfg, out)
    if a.stage == "build":
        return stage_build(cfg, out)
    if a.stage == "controls":
        return stage_controls(cfg, out)
    if a.stage == "models":
        return stage_models(cfg, out, a.only or None, a.max_steps)
    if a.stage == "package":
        return stage_package(cfg, out)
    return 2


if __name__ == "__main__":
    sys.exit(main())
