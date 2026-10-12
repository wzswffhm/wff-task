# -*- coding: utf-8 -*-
"""run_opus218.py —— 带重跑的 Opus 5 ×3 驱动（4router.net 端点）。

背景：4router.net 在账号池紧张时会回 HTTP 200 + 一句说明文本（无真实输出）。
agent_harness 已能识别并重试单步，但整轮仍可能整体失败；本脚本在**轮次**层面
再兜一层：某轮判 INVALID 且归因属传输层/上游不可用时，清掉该轮目录重跑，
直到 VALID 或达到最大尝试次数。

产物写到 --out（默认 _qc_runs/wlogseg-build/opus218-out，flat 布局），
全部 3 轮 VALID 后再同步进题包 extras/model_runs/opus-5（--sync 控制）。

用法：
    python -u run_opus218.py [--attempts 5] [--sync]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import time

ROOT = r"C:\Users\Administrator\Desktop\wff-task"
SKILL_SCRIPTS = os.path.join(ROOT, "harbor-windows", "skills", "harbor-windows", "scripts")
PKG = os.path.join(ROOT, "harbor-windows", "wfflab__wlogseg-218-v1.0.0-delivery")
OUT = os.path.join(ROOT, "harbor-windows", "_qc_runs", "wlogseg-build", "opus218-out")
CFG = os.path.join(os.environ.get("TEMP", "/tmp"), "wff-opus4router.endpoints.json")

RETRYABLE = ("upstream_unavailable", "transport_error", "http_5", "http_429",
             "http_0", "http_408", "http_502", "http_503", "http_504")


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=int, default=5)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--sync", action="store_true", help="全部 VALID 后同步进题包")
    a = ap.parse_args()

    sys.path.insert(0, SKILL_SCRIPTS)
    import run_model_validation as rmv  # noqa: E402

    rmv.LAYOUT = "flat"

    with io.open(CFG, encoding="utf-8") as fh:
        cfg = json.load(fh)
    ep = cfg["endpoints"][0]
    ep["runs"] = a.runs

    task_dir = PKG
    tid = os.path.basename(PKG.rstrip("\\/"))
    out_root = os.path.abspath(a.out)
    instr = rmv.load_instruction(task_dir)
    prompt = "请依据以下题面完成任务。\n\n---\n{instruction}\n".replace("{instruction}", instr or "")

    log("task_dir=%s" % task_dir)
    log("out_root=%s  layout=flat → model_runs 落在 <out>/<tid>/extras/model_runs" % out_root)
    log("endpoint=%s model=%s max_tokens=%s request_timeout=%s"
        % (ep["base_url"], ep["model"], ep["max_tokens"], ep.get("request_timeout")))

    results = {}
    for n in range(1, a.runs + 1):
        rd = rmv.run_dir(out_root, tid, ep["dir"], n)
        status = None
        for attempt in range(1, a.attempts + 1):
            if os.path.isdir(rd):
                shutil.rmtree(rd, ignore_errors=True)
            log("run-%d attempt %d/%d 开跑" % (n, attempt, a.attempts))
            try:
                res = rmv.run_once(task_dir, tid, ep, n, out_root, prompt,
                                   agent=True, instruction=instr)
            except Exception as e:  # noqa: BLE001
                log("run-%d attempt %d 异常: %s: %s" % (n, attempt, type(e).__name__, e))
                res = {"status": "INVALID", "meta": {"invalid_reason": "driver_exception"}}
            meta = res.get("meta") or {}
            status = res.get("status")
            reason = meta.get("invalid_reason")
            log("run-%d attempt %d → %s (%s) steps=%s out_tokens=%s patch=%s elapsed=%ss"
                % (n, attempt, status, reason, meta.get("steps"),
                   meta.get("output_tokens"), meta.get("patch_bytes"),
                   meta.get("elapsed")))
            if status == "VALID":
                break
            retryable = any(k in str(reason) for k in RETRYABLE)
            if not retryable:
                log("run-%d 非传输层失败，停止重跑" % n)
                break
            if attempt < a.attempts:
                time.sleep(20)
        results[n] = status

    ok = sum(1 for v in results.values() if v == "VALID")
    log("汇总：VALID=%d/%d  %s" % (ok, a.runs, results))

    if a.sync and ok == a.runs:
        src = os.path.join(out_root, tid, "extras", "model_runs", ep["dir"])
        dst = os.path.join(task_dir, "extras", "model_runs", ep["dir"])
        if os.path.isdir(dst):
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        log("已同步到题包：%s" % dst)
    elif a.sync:
        log("未全部 VALID，跳过同步（题包保持原状）")
    return 0 if ok == a.runs else 1


if __name__ == "__main__":
    sys.exit(main())
