"""校验 assemble_216_jobs_archive.py 的产物：结构完整性 + 自洽性 + 未改动原始证据。

用法：python -X utf8 _qc_runs/tools/verify_216_jobs_archive.py [--root DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_ID = "wfflab__wchunk-216"
DEFAULT_ROOT = WS / "deliverables" / "2026-10-11_wchunk216-jobs-archive" / TASK_ID
QCJOBS = WS / "_qc_runs" / "qc-216d-20261010-014419" / "jobs"
RUNS = WS / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / "runs" / TASK_ID

TRIAL_ALWAYS = ["config.json", "lock.json", "result.json", "trial.log",
                "artifacts/manifest.json",
                "artifacts/original-job/config.json", "artifacts/original-job/lock.json",
                "artifacts/original-job/result.json", "artifacts/original-job/job.log",
                "verifier/result.json", "verifier/reward.txt"]

# 投影生成的派生文件（不是原始证据，单独校验）
DERIVED = {("control", "verifier/result.json")}

problems: list[str] = []
oks: list[str] = []


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check(cond: bool, msg: str) -> None:
    (oks if cond else problems).append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    jobs = root / "jobs"

    # 1) 批次级文件
    for f in ("config.json", "result.json", "lock.json", "job.log", "ARCHIVE-NOTES.md"):
        check((jobs / f).is_file(), f"jobs/{f} 存在")
    cfg = json.loads((jobs / "config.json").read_text(encoding="utf-8"))
    res = json.loads((jobs / "result.json").read_text(encoding="utf-8"))
    lock = json.loads((jobs / "lock.json").read_text(encoding="utf-8"))
    check(cfg["schema"] == "harbor-independent-jobs-archive-v1", "config schema")
    check(cfg["archive_only"] is True, "config archive_only")
    check(cfg["n_trials"] == len(cfg["trials"]) == 14, f"n_trials = {cfg['n_trials']}")
    check(res["n_total_trials"] == len(res["trials"]) == 14, f"n_total_trials = {res['n_total_trials']}")
    check([t["trial_name"] for t in cfg["trials"]] == [t["trial_name"] for t in res["trials"]],
          "config/result trial 顺序一致")

    # 2) 每个 trial 的必备文件
    for entry in cfg["trials"]:
        t = entry["trial_name"]
        for rel in TRIAL_ALWAYS:
            check((jobs / t / rel).is_file(), f"{t}/{rel}")
        model = "runner" in entry["original_job_name"]
        if model:
            for rel in ("agent/agent.log", "agent/trajectory.jsonl", "agent/model-result.json",
                        "verifier/test-stdout.txt", "verifier/raw-runner-result.json",
                        "verifier/checks.json", "verifier/test.log", "verifier/stderr.log"):
                check((jobs / t / rel).is_file(), f"{t}/{rel}")
        else:
            check((jobs / t / "agent").is_dir(), f"{t}/agent 目录存在")
            if "-oracle-" in entry["original_job_name"]:
                check((jobs / t / "agent" / "oracle.txt").is_file(), f"{t}/agent/oracle.txt")
            for rel in ("verifier/report.json", "verifier/test-stdout.txt"):
                check((jobs / t / rel).is_file(), f"{t}/{rel}")

    # 3) reward 自洽：trial result.json ↔ verifier/result.json ↔ verifier/reward.txt
    for entry in cfg["trials"]:
        t = entry["trial_name"]
        tr = json.loads((jobs / t / "result.json").read_text(encoding="utf-8"))
        vr = json.loads((jobs / t / "verifier" / "result.json").read_text(encoding="utf-8"))
        reward = tr["verifier_result"]["rewards"]["reward"]
        check(float(reward) == float(vr["score"]), f"{t} reward {reward} == verifier score {vr['score']}")
        check((jobs / t / "verifier" / "reward.txt").read_text(encoding="utf-8").strip() == str(int(reward)),
              f"{t} reward.txt == {reward}")

    # 4) trajectory.jsonl 合法且非空
    for entry in cfg["trials"]:
        t = entry["trial_name"]
        p = jobs / t / "agent" / "trajectory.jsonl"
        if not p.is_file():
            continue
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        check(len(lines) > 0, f"{t} trajectory 行数 {len(lines)}")
        bad = 0
        for l in lines:
            try:
                json.loads(l)
            except json.JSONDecodeError:
                bad += 1
        check(bad == 0, f"{t} trajectory 全部为合法 JSON（坏行 {bad}）")

    # 5) 控制轮：与原 QC 目录逐字节比对（未改动）
    for entry in cfg["trials"]:
        if "runner" in entry["original_job_name"]:
            continue
        t = entry["trial_name"]
        src = QCJOBS / entry["original_job_name"] / t
        diff = 0
        n = 0
        for p in sorted(x for x in src.rglob("*") if x.is_file()):
            rel = p.relative_to(src)
            dst = jobs / t / rel
            n += 1
            if not dst.is_file() or sha256_file(dst) != sha256_file(p):
                diff += 1
        check(n > 0 and diff == 0, f"{t} 原生 trial {n} 个文件逐字节一致（差异 {diff}）")
        # 派生文件：verifier/result.json 必须是 report.json 的字段投影
        vr = json.loads((jobs / t / "verifier" / "result.json").read_text(encoding="utf-8"))
        rep = json.loads((jobs / t / "verifier" / "report.json").read_text(encoding="utf-8-sig"))
        check(vr.get("derived_from") == "verifier/report.json", f"{t} verifier/result.json 标注 derived_from")
        check(vr["score"] == rep["verdict"] and vr["status"] == rep["run_validity"],
              f"{t} verifier 投影 score/status == report.json")
        check([i["test_id"] for i in vr["items"]] == [c["test_id"] for c in rep["cases"]],
              f"{t} verifier 投影 items == report cases")
        # job 级原始件
        for f in ("config.json", "lock.json", "result.json", "job.log"):
            a = QCJOBS / entry["original_job_name"] / f
            b = jobs / t / "artifacts" / "original-job" / f
            check(b.is_file() and sha256_file(a) == sha256_file(b), f"{t} original-job/{f} 一致")

    # 6) 模型轮：与 runner runs 原始证据逐字节比对
    for entry in cfg["trials"]:
        if "runner" not in entry["original_job_name"]:
            continue
        run_id = entry["evidence_source"]["run_id"]
        label = entry["evidence_source"]["label"]
        src = RUNS / run_id / label
        t = entry["trial_name"]
        pairs = [("agent.log", "agent/agent.log"), ("result.json", "verifier/raw-runner-result.json"),
                 ("checks.json", "verifier/checks.json"), ("test.log", "verifier/test.log"),
                 ("stderr.log", "verifier/stderr.log")]
        for a, b in pairs:
            check(sha256_file(src / a) == sha256_file(jobs / t / b), f"{t} {b} == runs/{a}")

    # 7) lock.json 的 source_mapping 覆盖全部文件（除 lock.json 自身）且 sha256 正确
    mapped = {m["to"] for m in lock["source_mapping"]}
    on_disk = {f"{TASK_ID}/{p.relative_to(root).as_posix()}"
               for p in root.rglob("*") if p.is_file()
               and p.relative_to(root).as_posix() != "jobs/lock.json"}
    check(mapped == on_disk, f"source_mapping 覆盖全部文件（mapping {len(mapped)} / disk {len(on_disk)}）")
    bad = [m for m in lock["source_mapping"]
           if sha256_file(root / m["to"][len(TASK_ID) + 1:]) != m["sha256"]]
    check(not bad, f"source_mapping sha256 全部正确（不符 {len(bad)}）")

    # 8) identity 缺项如实记录
    no_identity = [t["trial_name"] for t in cfg["trials"]
                   if "runner" in t["original_job_name"] and not (jobs / t["trial_name"] / "agent" / "task_identity.json").is_file()]
    check(len(no_identity) == 7, f"缺 task_identity 的模型轮 = {len(no_identity)}（预期 7）")
    print("缺 task_identity 的轮次：")
    for t in no_identity:
        print("   -", t)

    print(f"\n通过 {len(oks)} 项；问题 {len(problems)} 项")
    for p in problems:
        print("  [FAIL]", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
