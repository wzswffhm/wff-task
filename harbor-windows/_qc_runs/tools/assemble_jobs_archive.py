#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""参数化的 jobs 归档器（wfflab__wfmt-215 / wfflab__wchunk-216 通用）。

背景
----
本题包线的 jobs/ 归档由两段工序产生：

  1) ``assemble_216_jobs_archive.py`` —— 把本地 Outside-Harbor runner 的 runs 轮次
     组装成 harbor-record-42 口径的 jobs 树（trial 名为 ``<task_id>__<label>-NN-<hash4>``）。
     该脚本是 1.2.0 一次性硬编码的。
  2) ``build_216_dist.py`` —— 把 jobs 树里的 trial 改名成 ``task__XXXXXXX``（模型轮）
     与 ``task0__XXXXXXX``（控制轮），并同步 config/result/lock 里的 trial_name。

本脚本把这两段合成一步，并参数化到两个包：

  * **复用**第 1 段的全部构造逻辑（不复制、不改写原脚本）：把原脚本源码做定点
    参数化替换后 exec 成模块，再覆盖其模块级常量后调用它的 ``main()``。
  * **吸收**第 2 段的改名与索引同步逻辑，改用与 ``build_216_dist.py`` 完全一致的
    ``short_id()``（sha256 → 7 位 base62，确定性、可复现）。
  * 轮次**自动发现**：只认 ``run_validity == VALID`` 的轮次；某个 label 数量不足时
    直接报错退出，绝不静默凑数。

所有原始产物逐字节复制，不新增执行、不新增评分、不改写任何日志。

用法
----
::

  python -X utf8 assemble_jobs_archive.py ^
      --task-id wfflab__wchunk-216 ^
      --task-name wfflab/wchunk-216 ^
      --module wchunk ^
      --task-version 1.2.1 ^
      --package-root C:\\...\\wfflab__wchunk-216-v1.2.0-delivery ^
      --runs-dir C:\\...\\runner\\runs\\wfflab__wchunk-216 ^
      --original-download wfflab__wchunk-216-v1.2.0-delivery.zip ^
      --original-download-sha256 <sha256> ^
      --original-note "..."

加 ``--dry-run`` 只打印发现结果与将要写入的 trial 计划，不动任何文件。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import string
import sys
import types
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = TOOLS_DIR / "assemble_216_jobs_archive.py"

ALPHABET = string.ascii_letters + string.digits

# 轮次计划：label -> (role, 需要的有效轮数)
ROUND_PLAN = [
    ("no-change", "nop", 3),
    ("golden", "oracle", 3),
    ("glm-5.3", "candidate", 1),
    ("kimi-k3", "candidate", 1),
    ("opus-5", "candidate", 3),
    ("qwen3.8-max-0902", "candidate", 3),
]

# 模型别名（与 runner/.env.local 的 <ALIAS>_LABEL 对应）
ALIAS_OF = {
    "glm-5.3": "GLM",
    "kimi-k3": "KIMI",
    "opus-5": "OPUS",
    "qwen3.8-max-0902": "QWEN",
}

# 保留在 jobs/ 顶层、由后续工序写入的注解层文件（重建 jobs/ 前先备份）
CARRY_OVER = ("invalid-slots.json", "INVALID-SLOTS.md")


def short_id(name: str) -> str:
    """确定性 7 位 base62 后缀，与 build_216_dist.py 的实现逐字符一致。"""
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()
    n = int(h[:16], 16)
    out = []
    for _ in range(7):
        out.append(ALPHABET[n % len(ALPHABET)])
        n //= len(ALPHABET)
    return "".join(out)


def discover_rounds(runs_dir: Path, verbose: bool = True):
    """扫描 runs 目录，按 label 收集有效轮次。

    返回 (model_rounds, control_rounds, report)：
      model_rounds   [(alias, label, run_id), ...]
      control_rounds [(role, label, run_id), ...]
    """
    if not runs_dir.is_dir():
        raise SystemExit(f"runs 目录不存在：{runs_dir}")

    found: dict[str, list[str]] = {}
    skipped: list[str] = []

    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if run_dir.name.startswith("_"):
            continue
        for label_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            result_json = label_dir / "result.json"
            if not result_json.is_file():
                skipped.append(f"{run_dir.name}/{label_dir.name}: 无 result.json")
                continue
            try:
                doc = json.loads(result_json.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # noqa: BLE001
                skipped.append(f"{run_dir.name}/{label_dir.name}: result.json 解析失败 {exc}")
                continue
            if doc.get("run_validity") != "VALID":
                skipped.append(f"{run_dir.name}/{label_dir.name}: run_validity={doc.get('run_validity')}")
                continue
            label = (doc.get("runner") or {}).get("label") or label_dir.name
            found.setdefault(label, []).append(run_dir.name)

    if verbose:
        print("发现的有效轮次：")
        for label in sorted(found):
            print(f"  {label:<22} {len(found[label])} 轮")

    model_rounds: list[tuple[str, str, str]] = []
    control_rounds: list[tuple[str, str, str]] = []
    problems: list[str] = []

    for label, role, need in ROUND_PLAN:
        have = sorted(found.get(label, []))
        if len(have) < need:
            problems.append(f"label={label}（{role}）有效轮次不足：需要 {need}，实际 {len(have)}")
            continue
        for run_id in have[:need]:
            if role == "candidate":
                model_rounds.append((ALIAS_OF.get(label, label.upper()), label, run_id))
            else:
                control_rounds.append((role, label, run_id))

    if problems:
        print("\n轮次不足，拒绝归档：", file=sys.stderr)
        for p in problems:
            print(f"  !! {p}", file=sys.stderr)
        if skipped:
            print("被跳过的轮次：", file=sys.stderr)
            for s in skipped:
                print(f"  - {s}", file=sys.stderr)
        raise SystemExit(2)

    return model_rounds, control_rounds, {"skipped": skipped, "found": found}


def build_base_module(module_name: str, task_version: str):
    """把 216 的归档脚本定点参数化后 exec 成模块（不修改原文件）。"""
    if not BASE_SCRIPT.is_file():
        raise SystemExit(f"基础归档脚本不存在：{BASE_SCRIPT}")
    src = BASE_SCRIPT.read_text(encoding="utf-8")

    subs = [
        # oracle 轮的参考解/工作区 tree hash：包内模块名（wchunk / wfmt）
        ('SRC / "environment" / "workspace" / "wchunk"',
         f'SRC / "environment" / "workspace" / "{module_name}"'),
        ('VER_SRC / "oracle" / "reference" / "wchunk"',
         f'VER_SRC / "oracle" / "reference" / "{module_name}"'),
        # 同两处的说明文案
        ("workspace/wchunk", f"workspace/{module_name}"),
        ("reference/wchunk", f"reference/{module_name}"),
        # 文案里的版本号
        ("task_version=1.2.0", f"task_version={task_version}"),
        ("v1.2.0 上的替代证据集", f"v{task_version} 上的替代证据集"),
        ("随 v1.2.0 交付 zip", f"随 v{task_version} 交付 zip"),
    ]
    for old, new in subs:
        hits = src.count(old)
        if hits == 0:
            raise SystemExit(f"参数化替换未命中，脚本可能已变动：{old!r}")
        src = src.replace(old, new)
        print(f"  参数化补丁 x{hits}: {old}  ->  {new}")

    mod = types.ModuleType("_assemble_base")
    mod.__file__ = str(BASE_SCRIPT)
    exec(compile(src, str(BASE_SCRIPT), "exec"), mod.__dict__)  # noqa: S102
    return mod


def rewrite_trial_names(jobs_dir: Path) -> dict[str, str]:
    """把 trial 目录改成 task__/task0__ 形态，并同步所有索引里的引用。"""
    rename: dict[str, str] = {}
    used: set[str] = set()

    for entry in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
        is_control = ("golden" in entry.name) or ("no-change" in entry.name)
        new_name = ("task0__" if is_control else "task__") + short_id(entry.name)
        if new_name in used:
            raise SystemExit(f"短 ID 冲突：{new_name}（{entry.name}）")
        used.add(new_name)
        rename[entry.name] = new_name

    for old, new in rename.items():
        (jobs_dir / old).rename(jobs_dir / new)

    for old, new in rename.items():
        cfg_path = jobs_dir / new / "config.json"
        if cfg_path.is_file():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            cfg["trial_name"] = new
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8", newline="\n")

    for fname in ("config.json", "result.json"):
        path = jobs_dir / fname
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        for entry in doc.get("trials", []):
            old = entry.get("trial_name")
            if old in rename:
                entry["trial_name"] = rename[old]
                if fname == "result.json":
                    entry["trial_result"] = f"{rename[old]}/result.json"
                    entry["original_job_result"] = f"{rename[old]}/artifacts/original-job/result.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")

    return rename


def refresh_lock(jobs_dir: Path, package_root: Path, root_name: str) -> int:
    """重算 lock.json：original_locks 跟随改名，source_mapping 用单根口径。"""
    lock_path = jobs_dir / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))

    mapping: list[dict] = []
    for path in sorted(p for p in package_root.rglob("*") if p.is_file()):
        rel = path.relative_to(package_root).as_posix()
        if rel == "jobs/lock.json":
            continue
        mapping.append({
            "from": f"{root_name}/{rel}", "to": f"{root_name}/{rel}",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        })

    # original_locks 的键是旧 trial 名；按 config.json 的顺序重建
    config = json.loads((jobs_dir / "config.json").read_text(encoding="utf-8-sig"))
    old_locks = lock.get("original_locks") or {}
    new_locks: dict[str, dict] = {}
    for entry in config.get("trials", []):
        trial = entry["trial_name"]
        for key, val in old_locks.items():
            if key == trial or key.endswith(trial):
                new_locks[trial] = val
                break
        else:
            # 兜底：按顺序一一对应（original_locks 与 trials 同源同序）
            idx = config["trials"].index(entry)
            keys = list(old_locks.keys())
            if idx < len(keys):
                new_locks[trial] = old_locks[keys[idx]]
    if len(new_locks) != len(old_locks):
        raise SystemExit(
            f"original_locks 重建失败：得到 {len(new_locks)} 项，原有 {len(old_locks)} 项")

    lock["original_locks"] = new_locks
    lock["source_mapping"] = mapping
    lock["layout_note"] = (
        "单根结构（参考 harbor-record-42）：zip 顶层只有 "
        f"{root_name}/，题包五件套与 jobs/ 都在该根下；判分侧材料在 {root_name}/verifier/。")
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    return len(mapping)


def patch_lock_notes(jobs_dir: Path, args) -> None:
    """改写 lock.json 里属于 216 v1.2.0 专有措辞的上游/zip 文案。

    基础归档脚本里 original_download_note 与 parent_zip_note 是硬编码字符串，
    对 215 或更高补丁版并不成立，因此在这里按本包实际情况覆盖。
    """
    lock_path = jobs_dir / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    if args.original_note:
        lock["original_download_note"] = args.original_note
    zip_name = args.original_download or ""
    if zip_name:
        lock["parent_zip_note"] = (
            f"本 jobs 树随交付 zip（{zip_name}）一起分发；zip 的 sha256 见同名 .sha256 文件；"
            "lock.json 位于 zip 内部，无法记录自身容器的 hash")
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    print("  已按本包实际情况改写 lock.json 的上游/zip 文案")


def carry_over_annotations(jobs_dir: Path, backups: dict[str, str], task_version: str) -> None:
    """把重建前备份的注解层写回，并把里面的版本号更新到当前包内版本。"""
    for name, text in backups.items():
        updated = text
        for old_ver in ("2.1.0", "1.2.0", "2.0.0", "1.1.0"):
            updated = updated.replace(f'"task_version_at_run": "{old_ver}"',
                                      f'"task_version_at_run": "{task_version}"')
        (jobs_dir / name).write_text(updated, encoding="utf-8", newline="\n")


def self_check(jobs_dir: Path, package_root: Path) -> list[str]:
    problems: list[str] = []
    for required in ("config.json", "result.json", "lock.json", "job.log"):
        if not (jobs_dir / required).is_file():
            problems.append(f"jobs/ 缺 {required}")

    trials = sorted(p.name for p in jobs_dir.iterdir() if p.is_dir())
    models = [t for t in trials if t.startswith("task__")]
    controls = [t for t in trials if t.startswith("task0__")]
    if len(trials) != 14 or len(models) != 8 or len(controls) != 6:
        problems.append(f"trial 命名/数量不符：total={len(trials)} task__={len(models)} task0__={len(controls)}")
    stray = [t for t in trials if not (t.startswith("task__") or t.startswith("task0__"))]
    if stray:
        problems.append(f"存在未改名的 trial：{stray}")

    cfg = json.loads((jobs_dir / "config.json").read_text(encoding="utf-8-sig"))
    res = json.loads((jobs_dir / "result.json").read_text(encoding="utf-8-sig"))
    for entry in cfg.get("trials", []):
        if not (jobs_dir / entry["trial_name"]).is_dir():
            problems.append(f"config.json 引用了不存在的 trial：{entry['trial_name']}")
    if cfg.get("n_trials") != len(trials):
        problems.append(f"config.n_trials={cfg.get('n_trials')} 与目录数 {len(trials)} 不符")
    for entry in res.get("trials", []):
        tr = jobs_dir / entry["trial_name"] / "result.json"
        if not tr.is_file():
            problems.append(f"result.json 引用了不存在的 trial result：{entry['trial_name']}")

    # 每个 trial 的必备零件
    for trial in trials:
        for rel in ("config.json", "lock.json", "result.json", "trial.log",
                    "agent", "verifier", "artifacts/original-job"):
            if not (jobs_dir / trial / rel).exists():
                problems.append(f"{trial} 缺 {rel}")

    lock = json.loads((jobs_dir / "lock.json").read_text(encoding="utf-8-sig"))
    for key in ("source_mapping", "original_locks", "task_hash_runner", "task_version"):
        if key not in lock:
            problems.append(f"lock.json 缺 {key}")
    if len(lock.get("original_locks") or {}) != len(trials):
        problems.append(f"original_locks={len(lock.get('original_locks') or {})} 与 trial 数 {len(trials)} 不符")

    # source_mapping 必须覆盖交付包（jobs/ 是它的子集）
    mapping = lock.get("source_mapping") or []
    if not any(entry["from"].endswith("instruction.md") for entry in mapping):
        problems.append("source_mapping 未覆盖题包（缺 instruction.md）")
    if any(entry["from"].endswith("jobs/lock.json") for entry in mapping):
        problems.append("source_mapping 不应包含 jobs/lock.json 自身")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="参数化 jobs 归档器（两包通用）")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--task-name", required=True, help="形如 wfflab/wchunk-216")
    ap.add_argument("--module", required=True, help="包内 python 模块名：wchunk / wfmt")
    ap.add_argument("--task-version", required=True, help="包内版本，如 1.2.1")
    ap.add_argument("--package-root", required=True,
                    help="交付包根目录（jobs/ 会被重建；同时作为 source_mapping 的根）")
    ap.add_argument("--runs-dir", required=True, help="runner 的 runs/<task_id> 目录")
    ap.add_argument("--original-download", default=None)
    ap.add_argument("--original-download-sha256", default=None)
    ap.add_argument("--original-note", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    package_root = Path(args.package_root).resolve()
    runs_dir = Path(args.runs_dir).resolve()
    jobs_dir = package_root / "jobs"
    root_name = package_root.name

    if not (package_root / "task.toml").is_file():
        raise SystemExit(f"--package-root 不像交付包根（缺 task.toml）：{package_root}")

    print(f"task_id      = {args.task_id}")
    print(f"task_version = {args.task_version}")
    print(f"package_root = {package_root}")
    print(f"root_name    = {root_name}")
    print(f"runs_dir     = {runs_dir}")
    print(f"jobs_dir     = {jobs_dir}")
    print()

    model_rounds, control_rounds, report = discover_rounds(runs_dir)

    print("\n轮次计划：")
    for alias, label, run_id in model_rounds:
        print(f"  candidate  {alias:<6} {label:<22} {run_id}")
    for role, label, run_id in control_rounds:
        print(f"  {role:<10} {'':<6} {label:<22} {run_id}")

    if args.dry_run:
        print("\n--dry-run：未改动任何文件。")
        return 0

    # 保留后续工序写入的注解层文件
    backups: dict[str, str] = {}
    for name in CARRY_OVER:
        src = jobs_dir / name
        if src.is_file():
            backups[name] = src.read_text(encoding="utf-8-sig")
            print(f"  备份注解层: jobs/{name}")

    print("\n参数化基础归档脚本：")
    base = build_base_module(args.module, args.task_version)

    # 覆盖模块级常量
    base.TASK_ID = args.task_id
    base.TASK_NAME = args.task_name
    base.TASK_VERSION = args.task_version
    base.SRC = package_root
    base.VER_SRC = package_root / "verifier"
    base.RUNS = runs_dir
    base.MODEL_ROUNDS = model_rounds
    base.CONTROL_ROUNDS = control_rounds
    base.DEFAULT_OUT = package_root
    base.DESCRIPTION = (
        f"Packaging-only aggregation of original independent runs on task version "
        f"{args.task_version}. No new execution, run ID, score, response or task checksum has "
        f"been created. Control trials (oracle/nop) and candidate model trials were produced by "
        f"the local Outside-Harbor runner "
        f"(deliverables/2026-10-04_outside-harbor-win/runner/runner.py) and are archived verbatim."
    )
    if args.original_download:
        base.ORIGINAL_DOWNLOAD = args.original_download
    if args.original_download_sha256:
        base.ORIGINAL_DOWNLOAD_SHA256 = args.original_download_sha256
    if args.original_note:
        base.ORIGINAL_DOWNLOAD_NOTE = args.original_note

    if not base.VER_SRC.is_dir():
        raise SystemExit(f"判分侧目录不存在：{base.VER_SRC}")

    print()
    sys.argv = ["assemble_jobs_archive", "--out", str(package_root)]
    rc = base.main()
    if rc != 0:
        raise SystemExit(f"基础归档器返回 {rc}")

    print("\n改名与索引同步：")
    rename = rewrite_trial_names(jobs_dir)
    for old, new in sorted(rename.items(), key=lambda kv: kv[1]):
        print(f"  {new}  <-  {old}")

    mapping_count = refresh_lock(jobs_dir, package_root, root_name)
    print(f"  source_mapping 覆盖 {mapping_count} 个文件")
    patch_lock_notes(jobs_dir, args)

    if backups:
        carry_over_annotations(jobs_dir, backups, args.task_version)
        print(f"  注解层写回: {', '.join(sorted(backups))}")

    # 归档器生成的 NOTES 不在交付形态里（现有两包都没有），保持与现有一致
    stray_notes = jobs_dir / "ARCHIVE-NOTES.md"
    if stray_notes.is_file():
        stray_notes.unlink()
        print("  已移除 ARCHIVE-NOTES.md（不在交付形态内）")

    print("\n自检：")
    problems = self_check(jobs_dir, package_root)
    if problems:
        for p in problems:
            print(f"  !! {p}")
        return 1
    print("  全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
