"""按新基础镜像批量重跑剩余题包的 12 轮。

每个包的处理顺序：
  1. 归档旧镜像下产生的 jobs/（作废证据留档，不删除）
  2. 控制组 Oracle x3 + NOP x3
  3. 模型轮 Qwen x3 + Opus x3
  4. 汇总打印

用法：
  python rerun_all_packages.py                 # 跑默认列表
  python rerun_all_packages.py wspawn-218      # 只跑指定包
"""
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

# (包名, build 目录, 模块名)
PACKAGES = [
    ("wspawn-218", "wspawn-build", "wspawn"),
    ("wvas-216", "wvas-build", "wvas"),
    ("wcancel-219", "wcancel-build", "wcancel"),
    ("wciocp-220", "wciocp-build", "wciocp"),
    ("wtoken-221", "wtoken-build", "wtoken"),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = HARBOR_SCRIPTS + os.pathsep + e.get("PATH", "")
    e["no_proxy"] = "*"
    e["NO_PROXY"] = "*"
    e["PYTHONIOENCODING"] = "utf-8"
    # Opus 走 4router 的 claude-opus-5（与 219/220 一致）
    e["wciocp_OPUS_MODEL"] = e.get("wciocp_OPUS_MODEL", "claude-opus-5")
    return e


def archive_old_jobs(pkg: Path, build: Path) -> None:
    jobs = pkg / "jobs"
    if not jobs.is_dir():
        log(f"  {pkg.name}: 无旧 jobs/")
        return
    dest = build / "jobs-old-image-20261015"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    try:
        shutil.move(str(jobs), str(dest))
        log(f"  {pkg.name}: 旧 jobs/ 已归档 -> {dest.name}")
    except Exception as exc:  # noqa: BLE001
        log(f"  !! {pkg.name}: 归档旧 jobs 失败 {type(exc).__name__}: {exc}")


def run(cmd: list, build: Path, label: str) -> int:
    log(f"  运行 {label}")
    r = subprocess.run(cmd, cwd=str(build), env=env(), capture_output=True, text=True, timeout=14400)
    tail = (r.stdout or "").strip().splitlines()[-12:]
    for line in tail:
        print("      " + line, flush=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()[-6:]
        for line in err:
            print("      ! " + line, flush=True)
    return r.returncode


def summarize(build: Path) -> None:
    for name, key in (("控制组", build / "controls" / "controls_summary.json"),
                      ("模型轮", build / "model-rounds" / "rounds_summary.json")):
        if not key.is_file():
            log(f"  {name}: 无汇总文件")
            continue
        try:
            data = json.loads(key.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            log(f"  {name}: 解析失败 {exc}")
            continue
        if isinstance(data, list):
            log(f"  {name}: {len(data)} 轮 -> " + ", ".join(
                f"{d.get('alias') or d.get('role')}#{d.get('index')}={d.get('reward')}" for d in data))
        else:
            log(f"  {name}: {data}")


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, build_name, mod in PACKAGES:
        if only and only != name:
            continue
        pkg = HW / f"wfflab__{name}-v1.0.0-delivery"
        build = HW / "_qc_runs" / build_name
        log("=" * 70)
        log(f"### {name}  ({pkg.name})")
        if not pkg.is_dir():
            log("  包目录不存在，跳过")
            continue
        if not (build / f"run_{mod}_controls.py").is_file():
            log(f"  缺 run_{mod}_controls.py，跳过")
            continue
        archive_old_jobs(pkg, build)
        rc1 = run([PY, str(build / f"run_{mod}_controls.py"), "--rounds", "3"], build, "控制组 6 轮")
        log(f"  控制组 exit={rc1}")
        summarize(build)
        rc2 = run([PY, str(build / f"run_{mod}_model_rounds.py"), "--max-steps", "40"], build, "模型轮 6 轮")
        log(f"  模型轮 exit={rc2}")
        summarize(build)
    log("批量重跑结束")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
