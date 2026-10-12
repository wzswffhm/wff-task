"""把 216 v1.2.0 的四目录布局重组为质检要求的单根结构（参考 harbor-record-42）。

质检意见（118 返修原因）：
  1. zip 顶层应只有同名目录 wfflab__wchunk-216-v1.2.0-delivery
  2. Task 根目录必须有 jobs/
  3. environment/adapter.toml 的 prepare/validate/run/restore/cleanup/workspace 入口要可解析
  4. jobs/ 必须是 14 个可识别的标准 Harbor job（task__* / task0__*）

重组后：
  wfflab__wchunk-216-v1.2.0-delivery/
    instruction.md  task.toml  source.json  platform_import.json
    environment/    （含 adapter.toml 扁平入口 + workspace/ + vendor/ + *.ps1）
    solution/       （入口，不含参考解）
    tests/          （公开测试入口）
    verifier/       （判分侧材料，原 outside_harbor-verifier 内容）
    jobs/           （42 格式：config/result/lock/job.log + task__×8 + task0__×6）

用法：python -X utf8 build_216_dist.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import string
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
REWORK = WS / "deliverables" / "2026-10-11_wchunk216-返修"
BUILD = REWORK / "build"
TASK_ID = "wfflab__wchunk-216"
VERSION = "1.2.0"
ROOT_NAME = f"{TASK_ID}-v{VERSION}-delivery"
DIST_ROOT = REWORK / "dist"
DIST = DIST_ROOT / ROOT_NAME

SRC_TASK = BUILD / "outside_harbor-assets" / TASK_ID
SRC_VER = BUILD / "outside_harbor-verifier" / TASK_ID
SRC_JOBS = BUILD / "jobs"

ALPHABET = string.ascii_letters + string.digits

FLAT_ENTRIES = """# Standard Harbor entry points (flat keys). The reviewer resolves these names
# directly; the [table] sections below are this repo's local-runner binding.
prepare = "prepare.ps1"
validate = "validate_environment.ps1"
run = "run.ps1"
restore = "restore.ps1"
cleanup = "cleanup.ps1"
workspace = "workspace"
start = "run.ps1"
test = "../tests/test.ps1"
exec_agent = "workspace"

"""


def short_id(name: str) -> str:
    """确定性 7 位 base62 后缀（同参考包的 task__XXXXXXX 形态，可复现）。"""
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()
    n = int(h[:16], 16)
    out = []
    for _ in range(7):
        out.append(ALPHABET[n % len(ALPHABET)])
        n //= len(ALPHABET)
    return "".join(out)


def copytree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", "*.pyc", ".DS_Store"))


def main() -> int:
    if not SRC_TASK.is_dir() or not SRC_VER.is_dir() or not SRC_JOBS.is_dir():
        raise SystemExit("缺少输入目录：先跑 stage1-4 与 assemble_216_jobs_archive.py")
    if DIST_ROOT.exists():
        shutil.rmtree(DIST_ROOT)
    DIST.mkdir(parents=True)

    # ---- 1. 五件套平铺到单根（排除运行产物） ----
    SKIP_TOP = {"results", "runs", "work", "logs", "__pycache__", ".pytest_cache",
                ".git", "node_modules"}
    # 参考包 harbor-record-42 的根级只有 instruction.md/task.toml + 4 个目录，
    # 不包含 source.json / platform_import.json，因此交付拷贝里也去掉。
    SKIP_ROOT_FILES = {"source.json", "platform_import.json"}
    for item in sorted(SRC_TASK.iterdir()):
        if item.name in SKIP_TOP or item.name in SKIP_ROOT_FILES:
            print(f"  skip (not in reference package): {item.name}")
            continue
        if item.is_dir():
            copytree(item, DIST / item.name)
        else:
            shutil.copy2(item, DIST / item.name)
    print(f"root files : {sorted(p.name for p in DIST.iterdir())}")

    # ---- 2. 判分侧材料 → verifier/ ----
    copytree(SRC_VER, DIST / "verifier")
    print("verifier/  : copied judge-side material")

    # ---- 3. adapter.toml 加扁平入口键 ----
    adapter = DIST / "environment" / "adapter.toml"
    text = adapter.read_text(encoding="utf-8-sig")
    if "prepare = " not in text:
        adapter.write_text(FLAT_ENTRIES + text, encoding="utf-8", newline="\n")
        print("adapter    : flat entry keys prepended")
    else:
        print("adapter    : flat keys already present")

    # ---- 4. jobs/ 重建为 task__/task0__ 命名 ----
    dst_jobs = DIST / "jobs"
    dst_jobs.mkdir(parents=True, exist_ok=True)
    for fname in ("config.json", "result.json", "lock.json", "job.log"):
        src = SRC_JOBS / fname
        if src.is_file():
            shutil.copy2(src, dst_jobs / fname)

    rename: dict[str, str] = {}
    for d in sorted(p for p in SRC_JOBS.iterdir() if p.is_dir()):
        is_control = ("golden" in d.name) or ("no-change" in d.name)
        new_name = ("task0__" if is_control else "task__") + short_id(d.name)
        if new_name in rename.values():
            raise SystemExit(f"短 ID 冲突：{new_name}")
        rename[d.name] = new_name
        copytree(d, dst_jobs / new_name)
        # trial 级 config.json 里的 trial_name 要同步
        cfg_path = dst_jobs / new_name / "config.json"
        if cfg_path.is_file():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            cfg["trial_name"] = new_name
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8", newline="\n")
    print(f"jobs trials: {len(rename)} renamed")
    for old, new in sorted(rename.items(), key=lambda kv: kv[1]):
        print(f"  {new}  <-  {old}")

    # ---- 5. 索引文件里的 trial_name / 路径同步 ----
    for fname in ("config.json", "result.json"):
        path = dst_jobs / fname
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        for entry in doc["trials"]:
            old = entry["trial_name"]
            new = rename.get(old, old)
            entry["trial_name"] = new
            if fname == "result.json":
                entry["trial_result"] = f"{new}/result.json"
                entry["original_job_result"] = f"{new}/artifacts/original-job/result.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")

    lock_path = dst_jobs / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
    lock["original_locks"] = {
        rename.get(k, k): v for k, v in (lock.get("original_locks") or {}).items()
    }
    # source_mapping：重算为单根口径（排除 jobs/lock.json 自身）
    mapping = []
    for p in sorted(q for q in DIST.rglob("*") if q.is_file()):
        rel = p.relative_to(DIST).as_posix()
        if rel == "jobs/lock.json":
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        mapping.append({"from": f"{ROOT_NAME}/{rel}", "to": f"{ROOT_NAME}/{rel}",
                        "sha256": h, "size": p.stat().st_size})
    lock["source_mapping"] = mapping
    lock["layout_note"] = (
        "单根结构（参考 harbor-record-42）：zip 顶层只有 "
        f"{ROOT_NAME}/，题包五件套与 jobs/ 都在该根下；判分侧材料在 {ROOT_NAME}/verifier/。")
    lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    print(f"source_mapping: {len(mapping)} files")

    # ---- 6. 结构自检 ----
    problems = []
    for required in ("instruction.md", "task.toml", "environment", "solution", "tests", "jobs"):
        if not (DIST / required).exists():
            problems.append(f"根目录缺 {required}")
    adapter_text = (DIST / "environment" / "adapter.toml").read_text(encoding="utf-8-sig")
    for key in ("prepare", "validate", "run", "restore", "cleanup", "workspace"):
        if f"{key} = " not in adapter_text:
            problems.append(f"adapter.toml 缺扁平入口 {key}")
    trials = [p.name for p in dst_jobs.iterdir() if p.is_dir()]
    models = [t for t in trials if t.startswith("task__")]
    controls = [t for t in trials if t.startswith("task0__")]
    if len(trials) != 14 or len(models) != 8 or len(controls) != 6:
        problems.append(f"trial 命名/数量不符：total={len(trials)} task__={len(models)} task0__={len(controls)}")
    for entry in json.loads((dst_jobs / "config.json").read_text(encoding="utf-8-sig"))["trials"]:
        if not (dst_jobs / entry["trial_name"]).is_dir():
            problems.append(f"config.json 引用了不存在的 trial：{entry['trial_name']}")

    print()
    print(f"DIST     = {DIST}")
    print(f"problems = {len(problems)}")
    for p in problems:
        print(f"  !! {p}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
