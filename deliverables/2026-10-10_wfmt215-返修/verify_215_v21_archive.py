"""验证 v2.1.0 返修包的 jobs 归档（2026-10-10_wfmt215-返修/build）。

断言分七组：
  1. 结构完整：14 个 trial 目录 + 4 个顶层文件 + 每个 trial 的必需文件
  2. 角色正确：候选轮有 agent.log/trajectory.jsonl；控制轮用 no-agent.json 声明
  3. 逐字节同源：verifier/raw-runner-result.json 与 runs 源文件完全一致（14/14）
  4. reward 自洽：trial result.json ↔ verifier/reward.txt ↔ verifier/result.json
  5. 身份绑定：14/14 有 task_identity.json，且其 task_hash 等于 lock.json 的 runner 口径
  6. source_mapping：覆盖 build/ 下全部文件（除 jobs/lock.json），sha256/size 逐一正确
  7. 门禁断言：oracle×3=1、nop×3=0、QWEN×3=0、OPUS=[1,0,1]、KIMI=0、GLM=0

用法：python -X utf8 _qc_runs/tools/verify_215_v21_archive.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
BUILD = WS / "deliverables" / "2026-10-10_wfmt215-返修" / "build"
JOBS = BUILD / "jobs"
RUNS = WS / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / "runs" / "wfflab__wfmt-215"
TASK_ID = "wfflab__wfmt-215"

checks = 0
problems: list[str] = []


def ok(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        problems.append(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    cfg = read_json(JOBS / "config.json")
    res = read_json(JOBS / "result.json")
    lock = read_json(JOBS / "lock.json")

    # ---- 1. 结构与试验清单 -------------------------------------------------
    for name in ("config.json", "result.json", "lock.json", "job.log", "ARCHIVE-NOTES.md"):
        ok((JOBS / name).is_file(), f"缺顶层文件 jobs/{name}")
    trials = sorted(d.name for d in JOBS.iterdir() if d.is_dir())
    ok(len(trials) == 14, f"trial 目录数应为 14，实际 {len(trials)}")
    ok(cfg.get("n_trials") == 14, f"config.json n_trials 应为 14，实际 {cfg.get('n_trials')}")
    ok(res.get("n_total_trials") == 14, f"result.json n_total_trials 应为 14，实际 {res.get('n_total_trials')}")
    ok(cfg.get("archive_only") is True, "config.json 应声明 archive_only=true")
    ok(lock.get("task_version") == "2.1.0", f"lock.task_version 应为 2.1.0，实际 {lock.get('task_version')}")

    required = [
        "config.json", "lock.json", "result.json", "trial.log",
        "agent/model-result.json", "agent/task_identity.json",
        "agent/prompt.system.txt", "agent/prompt.task.txt",
        "artifacts/manifest.json", "artifacts/original-job/config.json",
        "artifacts/original-job/lock.json", "artifacts/original-job/result.json",
        "artifacts/original-job/job.log",
        "verifier/checks.json", "verifier/raw-runner-result.json", "verifier/result.json",
        "verifier/report.json", "verifier/reward.txt", "verifier/stderr.log",
        "verifier/test.log", "verifier/test-stdout.txt",
    ]

    # 由 config.json 拿到 run_id/label，供同源比对用
    run_of: dict[str, tuple[str, str]] = {}
    for entry in cfg["trials"]:
        ev = entry.get("evidence_source") or {}
        run_of[entry["trial_name"]] = (ev.get("run_id"), ev.get("label"))

    for trial in trials:
        base = JOBS / trial
        for rel in required:
            ok((base / rel).is_file(), f"{trial}: 缺 {rel}")
        # ---- 2. 角色正确 ---------------------------------------------------
        is_candidate = "candidate" in (run_of.get(trial, ("", ""))[0] or "")
        if is_candidate:
            ok((base / "agent" / "agent.log").is_file(), f"{trial}: 候选轮缺 agent/agent.log")
            traj = base / "agent" / "trajectory.jsonl"
            ok(traj.is_file(), f"{trial}: 候选轮缺 agent/trajectory.jsonl")
            if traj.is_file():
                lines = [ln for ln in traj.read_text(encoding="utf-8").splitlines() if ln.strip()]
                ok(len(lines) > 0, f"{trial}: trajectory.jsonl 为空")
                bad = 0
                for ln in lines:
                    try:
                        json.loads(ln)
                    except json.JSONDecodeError:
                        bad += 1
                ok(bad == 0, f"{trial}: trajectory.jsonl 有 {bad} 行不是合法 JSON")
        else:
            ok((base / "agent" / "no-agent.json").is_file(), f"{trial}: 控制轮缺 agent/no-agent.json")
            ok(not (base / "agent" / "agent.log").exists(), f"{trial}: 控制轮不应有 agent.log")

        # ---- 3. 逐字节同源 -------------------------------------------------
        run_id, label = run_of.get(trial, (None, None))
        ok(bool(run_id and label), f"{trial}: config.json 缺 evidence_source.run_id/label")
        if run_id and label:
            src_result = RUNS / run_id / label / "result.json"
            ok(src_result.is_file(), f"{trial}: runs 源缺 result.json（{src_result}）")
            if src_result.is_file():
                ok(sha256(src_result) == sha256(base / "verifier" / "raw-runner-result.json"),
                   f"{trial}: verifier/raw-runner-result.json 与 runs 源不一致")
            src_checks = RUNS / run_id / label / "checks.json"
            if src_checks.is_file():
                ok(sha256(src_checks) == sha256(base / "verifier" / "checks.json"),
                   f"{trial}: verifier/checks.json 与 runs 源不一致")

        # ---- 4. reward 自洽 ------------------------------------------------
        tr = read_json(base / "result.json")
        reward = tr["verifier_result"]["rewards"]["reward"]
        txt = (base / "verifier" / "reward.txt").read_text(encoding="utf-8").strip()
        # reward.txt 用整数写法（与 Harbor 原生一致），result.json 用浮点，按数值比较。
        ok(abs(float(txt) - float(reward)) < 1e-9,
           f"{trial}: reward.txt({txt}) != result.json reward({reward})")
        vr = read_json(base / "verifier" / "result.json")
        ok(abs(float(vr.get("score")) - float(reward)) < 1e-9,
           f"{trial}: verifier/result.json score({vr.get('score')}) != {reward}")
        ok(vr.get("status") == "VALID", f"{trial}: verifier/result.json status 应为 VALID")
        ok(len(vr.get("items", [])) == 15, f"{trial}: verifier/result.json items 应为 15 项")

        # ---- 5. 身份绑定 ---------------------------------------------------
        ident = read_json(base / "agent" / "task_identity.json")
        ok(ident.get("task_version") == "2.1.0", f"{trial}: task_identity.task_version 应为 2.1.0")
        ok(ident.get("task_hash") == lock.get("task_hash_runner"),
           f"{trial}: task_identity.task_hash 与 lock.task_hash_runner 不一致")
        ok((ident.get("docker_image_digest") or "").startswith("sha256:"),
           f"{trial}: task_identity 缺 image_digest")

    # ---- 6. source_mapping 覆盖与哈希 --------------------------------------
    mapping = {m["from"]: m for m in lock["source_mapping"]}
    on_disk = [p for p in sorted(BUILD.rglob("*")) if p.is_file()]
    rel_disk = {p.relative_to(BUILD).as_posix(): p for p in on_disk}
    ok("jobs/lock.json" not in mapping, "source_mapping 不应包含 jobs/lock.json（自引用）")
    missing = sorted(r for r in rel_disk if r != "jobs/lock.json" and r not in mapping)
    ok(not missing, f"source_mapping 漏了 {len(missing)} 个文件，例如 {missing[:3]}")
    extra = sorted(r for r in mapping if r not in rel_disk)
    ok(not extra, f"source_mapping 多出 {len(extra)} 个不存在的条目，例如 {extra[:3]}")
    mismatch = []
    for rel, entry in mapping.items():
        path = rel_disk.get(rel)
        if path is None:
            continue
        if entry.get("size") != path.stat().st_size or entry.get("sha256") != sha256(path):
            mismatch.append(rel)
    ok(not mismatch, f"source_mapping 有 {len(mismatch)} 个 sha256/size 不匹配，例如 {mismatch[:3]}")

    # ---- 7. 门禁断言 -------------------------------------------------------
    reward_by_trial = {t: read_json(JOBS / t / "result.json")["verifier_result"]["rewards"]["reward"]
                       for t in trials}

    def group(prefix: str) -> list[float]:
        return [v for k, v in reward_by_trial.items() if k.startswith(f"{TASK_ID}__{prefix}")]

    oracle = group("golden")
    nop = group("no-change")
    qwen = group("qwen3.8-max-0902")
    opus = group("opus-5")
    kimi = group("kimi-k3")
    glm = group("glm-5.3")
    ok(len(oracle) == 3 and all(v == 1 for v in oracle), f"oracle 应 3 轮全 1，实际 {oracle}")
    ok(len(nop) == 3 and all(v == 0 for v in nop), f"nop 应 3 轮全 0，实际 {nop}")
    ok(len(qwen) == 3, f"QWEN 应 3 轮，实际 {qwen}")
    ok(len(opus) == 3, f"OPUS 应 3 轮，实际 {opus}")
    ok(len(kimi) == 1, f"KIMI 应 1 轮，实际 {kimi}")
    ok(len(glm) == 1, f"GLM 应 1 轮，实际 {glm}")
    if len(opus) == 3 and len(qwen) == 3:
        ok(sum(opus) > sum(qwen), f"区分度门禁失败：OPUS 总分 {sum(opus)} 未严格大于 QWEN {sum(qwen)}")

    # ARCHIVE-NOTES 的 trial 表行数
    notes = (JOBS / "ARCHIVE-NOTES.md").read_text(encoding="utf-8")
    table_rows = [ln for ln in notes.splitlines()
                  if ln.startswith(f"| `{TASK_ID}__")]
    ok(len(table_rows) == 14, f"ARCHIVE-NOTES.md 的 trial 表应有 14 行，实际 {len(table_rows)}")

    print(f"checks   : {checks}")
    print(f"problems : {len(problems)}")
    for p in problems:
        print(f"  !! {p}")
    print("verdict  :", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
