# -*- coding: utf-8 -*-
"""run_218_full_qc.py —— 用 2026-10-12 版甲方自检包对 218 交付 ZIP 跑完整质检。

流程（与甲方 SKILL 一致）：输入交付 ZIP → 安全解压 → 交付目录静态门禁 →
14 个原生 Harbor job 门禁 → 四模型准入 → 真实 Harbor Oracle/NOP（3+3）→ 汇总。

用法：
    python run_218_full_qc.py [--input <zip|dir>] [--out <dir>] [--attempts 3]
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
QC_SCRIPTS = ROOT / "harbor-windows" / "_qc_runs" / "qc-pkg-new" / "windows-harbor-qc" / "scripts"
BUILD = ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build"
DEFAULT_ZIP = (ROOT / "deliverables" / "2026-10-12_wlogseg218-交付" / "package"
               / "wfflab__wlogseg-218-v1.0.0-delivery.zip")
PY = Path(os.environ.get("HARBOR_PY",
                         r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\python.exe"))
HARBOR_SCRIPTS = Path(r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts")
DOCKER_BIN = r"C:\Program Files\Docker\Docker\resources\bin"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_ZIP))
    ap.add_argument("--out", default=str(BUILD / "qc-final-218"))
    ap.add_argument("--attempts", type=int, default=3)
    a = ap.parse_args()

    inp = Path(a.input)
    out = Path(a.out)
    if out.exists():
        # 甲方要求结果目录为空或不存在
        import shutil
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(HARBOR_SCRIPTS), DOCKER_BIN, env.get("PATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONPATH", None)

    cmd = [str(PY), str(QC_SCRIPTS / "run_delivery_qc.py"),
           "--input", str(inp), "--out", str(out), "--attempts", str(a.attempts)]
    print("input : %s" % inp)
    print("out   : %s" % out)
    t0 = time.time()
    log = out.parent / (out.name + ".log")
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        p = subprocess.run(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT)
    print("exit=%s elapsed=%ds  log=%s" % (p.returncode, int(time.time() - t0), log))

    rep_md = out / "report.md"
    rep_js = out / "report.json"
    if rep_md.is_file():
        head = rep_md.read_text(encoding="utf-8", errors="replace").splitlines()[:24]
        print("\n".join(head))
    if rep_js.is_file():
        doc = json.loads(rep_js.read_text(encoding="utf-8-sig"))
        print("\n--- 机器可读摘要 ---")
        print("verdict:", doc.get("verdict"))
        for key in ("layout", "model_gate", "model_jobs", "harbor"):
            v = doc.get(key) or {}
            print("  %-12s pass=%s conclusion=%s errors=%s"
                  % (key, v.get("pass"), v.get("conclusion"),
                     len(v.get("errors") or [])))
        errs = []
        for key in ("layout", "model_gate", "model_jobs", "harbor"):
            for e in ((doc.get(key) or {}).get("errors") or [])[:6]:
                errs.append("[%s] %s" % (key, e))
        for e in errs[:20]:
            print("   ", e)
    return 0 if (rep_js.is_file()
                 and json.loads(rep_js.read_text(encoding="utf-8-sig")).get("verdict") == "PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
