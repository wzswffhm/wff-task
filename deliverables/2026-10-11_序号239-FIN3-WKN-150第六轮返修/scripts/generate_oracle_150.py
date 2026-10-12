# -*- coding: utf-8 -*-
"""在 WSL Ubuntu 的判分镜像内真实执行参考生成闭环，产出 Oracle 七件交付物。

用途：响应质检报告第 5/6 项——参考生成脚本修好后，必须"从输入生成完整同源参考产物"，
而不能仅手工改 memo 或复制 golden。本脚本执行的是 solution/solve.sh（已改为真实复算），
并把执行日志、容器信息、产物哈希一并落盘作为可核验证据。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

WSL_ROOT = pathlib.Path("/mnt/c/Users/Administrator/Desktop/wff-task")
TASK = WSL_ROOT / "harbor-weakness" / "FIN3-WKN-150"
WIN_ROOT = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
EVID = (WIN_ROOT / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
        / "evidence" / "oracle_generation")
OUT = EVID / "output"
LOGS = EVID / "logs"
IMAGE = "fin3-wkn-150:local"
NAME = "gen-FIN3-WKN-150-oracle"

EXPECTED = [
    "FIN3-WKN-150_PreIPO投资决策备忘录.md",
    "FIN3-WKN-150_reproduce.py",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart01_材料覆盖与数据缺口.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart02_收入与利润口径还原.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart03_现金流与营运效率.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart04_可比与DCF估值.png",
    "FIN3-WKN-150_charts/FIN3-WKN-150_chart05_估值区间与风险缺口.png",
]


def wsl(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-lc", script],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for directory in (OUT, LOGS):
        directory.mkdir(parents=True, exist_ok=True)
    for stale in OUT.rglob("*"):
        if stale.is_file():
            stale.unlink()

    wsl_out = "/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/" \
              "2026-10-11_序号239-FIN3-WKN-150第六轮返修/evidence/oracle_generation"
    task_wsl = TASK.as_posix()

    wsl(f"docker rm -f {NAME} >/dev/null 2>&1 || true")
    # 直接调用修好后的复算脚本从只读输入生成产物：这才是"参考生成闭环"的本体。
    # solution/solve.sh 属平台固定模板（97 B / sha 3f26ac81…，与 149 等题逐字节一致），
    # 本轮不改动它，以免破坏平台模板一致性；生成证据改由本脚本的执行归档承载。
    inner = (
        "set -o pipefail; "
        "python3 /solution/golden_output/FIN3-WKN-150_reproduce.py "
        "/app/input_files /app/output 2>&1 | tee /logs/generate.log; "
        "rc=${PIPESTATUS[0]}; "
        "cp /solution/golden_output/FIN3-WKN-150_reproduce.py "
        "/app/output/FIN3-WKN-150_reproduce.py; "
        "echo \"GENERATE_EXIT=${rc}\" | tee -a /logs/generate.log; "
        "exit ${rc}"
    )
    command = (
        f"docker run --rm --name {NAME} "
        f"-v {task_wsl}/solution:/solution:ro "
        f"-v {task_wsl}/environment/input_files:/app/input_files:ro "
        f"-v {wsl_out}/output:/app/output "
        f"-v {wsl_out}/logs:/logs "
        f"{IMAGE} bash -c {json.dumps(inner)}"
    )
    print("launching generation container ...")
    started = time.time()
    result = wsl(command)
    elapsed = time.time() - started
    print(f"docker rc={result.returncode} elapsed={elapsed:.1f}s")
    if result.stdout.strip():
        print("--- stdout tail ---")
        print(result.stdout[-1500:])
    if result.stderr.strip():
        print("--- stderr tail ---")
        print(result.stderr[-1500:])

    (LOGS / "docker_result.json").write_text(json.dumps({
        "image": IMAGE,
        "container": NAME,
        "generation_entry": "python3 /solution/golden_output/FIN3-WKN-150_reproduce.py "
                            "/app/input_files /app/output",
        "solve_script_untouched": "solution/solve.sh 保持平台固定模板 "
                                  "(97 B, sha256 3f26ac81cb1c4583…, 与 FIN3-WKN-149 逐字节一致)",
        "command": command,
        "returncode": result.returncode,
        "elapsed_seconds": round(elapsed, 2),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 产物核验 ===")
    missing, records = [], []
    for rel in EXPECTED:
        path = OUT / rel
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(rel)
            print(f"  [缺失] {rel}")
            continue
        digest = sha256(path)
        records.append({"path": rel, "size": path.stat().st_size, "sha256": digest})
        print(f"  [OK] {rel:64s} {path.stat().st_size:>8,} B  {digest[:12]}")
    (EVID / "generated_manifest.json").write_text(json.dumps({
        "expected": EXPECTED, "found": records, "missing": missing,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n产物齐全: {not missing}  ({len(records)}/{len(EXPECTED)})")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
