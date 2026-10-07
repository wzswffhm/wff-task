# -*- coding: utf-8 -*-
"""生成 swelive_spec.json / task.toml / platform_import.json / manifest.json，并计算 task_hash。"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
TASK_ID = "wfflab__wtask-216"
VERSION = "1.0"
WREF = "wfflab/wtask-windows-bench:wfflab__wtask-216-v1.0"

F2P = [
    "tests/test_wtask_semantics.py::test_daily_interval_anchored_at_start_boundary",
    "tests/test_wtask_semantics.py::test_weekly_honours_weeks_interval",
    "tests/test_wtask_semantics.py::test_monthly_restricted_to_listed_months",
    "tests/test_wtask_semantics.py::test_monthly_day_of_week_week_five_means_last_week",
    "tests/test_wtask_semantics.py::test_repetition_stops_before_duration",
    "tests/test_wtask_semantics.py::test_repetition_respects_end_boundary",
    "tests/test_wtask_semantics.py::test_disabled_trigger_is_skipped",
    "tests/test_wtask_semantics.py::test_duration_canonical_form",
    "tests/test_wtask_semantics.py::test_error_kinds_are_structured",
    "tests/test_wtask_semantics.py::test_execution_time_limit_zero_means_unlimited",
]
P2P = [
    "tests/test_wtask_semantics.py::test_parse_simple_daily_fields",
    "tests/test_wtask_semantics.py::test_time_trigger_fires_once",
    "tests/test_wtask_semantics.py::test_default_daily_interval_is_one",
    "tests/test_wtask_semantics.py::test_disabled_task_has_no_runs",
    "tests/test_wtask_semantics.py::test_plan_window_is_bounded_and_sorted",
    "tests/test_wtask_semantics.py::test_roundtrip_of_simple_daily_task",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def base_commit():
    """复现 Dockerfile 第 7 步的确定性基线 commit，取 rev-parse HEAD。"""
    tmp = tempfile.mkdtemp(prefix="wtask-baseline-")
    try:
        dst = os.path.join(tmp, "testbed")
        shutil.copytree(os.path.join(ROOT, "environment", "workspace"), dst)
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = "2026-10-04T00:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = "2026-10-04T00:00:00+00:00"
        g = ["git", "-c", "core.autocrlf=false", "-c", "core.longpaths=true",
             "-c", "commit.gpgsign=false"]
        subprocess.run(g + ["init", "-q"], cwd=dst, check=True, env=env)
        subprocess.run(g + ["config", "core.autocrlf", "false"], cwd=dst, check=True, env=env)
        subprocess.run(g + ["add", "-A"], cwd=dst, check=True, env=env)
        subprocess.run(g + ["-c", "user.email=bench@example.com",
                            "-c", "user.name=Terminal Bench",
                            "commit", "--allow-empty", "-qm", "baseline"],
                       cwd=dst, check=True, env=env)
        out = subprocess.run(g + ["rev-parse", "HEAD"], cwd=dst, check=True,
                             capture_output=True, text=True, env=env)
        return out.stdout.strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


instr = sha256(os.path.join(ROOT, "instruction.md"))
tp = sha256(os.path.join(ROOT, "tests", "test_patch.diff"))
orac = sha256(os.path.join(ROOT, "solution", "oracle.patch"))
dock = sha256(os.path.join(ROOT, "environment", "Dockerfile"))

payload = ("task_id=" + TASK_ID + "\n"
           + "task_version=" + VERSION + "\n"
           + "instruction_md_sha256=" + instr + "\n"
           + "test_patch_sha256=" + tp + "\n"
           + "oracle_patch_sha256=" + orac + "\n"
           + "dockerfile_sha256=" + dock)
task_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
commit = base_commit()
print("instruction", instr)
print("test_patch ", tp)
print("oracle     ", orac)
print("dockerfile ", dock)
print("base_commit", commit)
print("task_hash  ", task_hash)

# ---------------------------------------------------------------- swelive_spec
with open(os.path.join(ROOT, "..", "wfflab__wfmt-215", "tests", "swelive_spec.json"),
          encoding="utf-8") as fh:
    spec = json.load(fh)
spec["instance_id"] = TASK_ID
spec["task_version"] = VERSION
spec["task_hash"] = task_hash
spec["test_cmds"] = [
    "Set-Location C://testbed; Remove-Item reports -Recurse -Force -ErrorAction SilentlyContinue; "
    "New-Item -ItemType Directory -Force reports | Out-Null; "
    "python -m pytest -rA --tb=short -p no:cacheprovider --json-report "
    "--json-report-file=reports\\pytest-results.json tests\\test_wtask_semantics.py"
]
spec["print_cmds"] = ["Get-Content -Raw C:\\testbed\\reports\\pytest-results.json"]
spec["rebuild_cmds"] = [
    "Set-Location C:\\testbed; $env:PYTHONPATH=\"C:\\testbed;$env:PYTHONPATH\"; "
    "python -c \"import pytest, wtask\""
]
spec["FAIL_TO_PASS"] = F2P
spec["PASS_TO_PASS"] = P2P
spec["base_commit"] = commit
spec["source_commit"] = commit
spec["image_ref"] = WREF
spec["image_digest"] = "<PENDING_BUILD>"
with open(os.path.join(ROOT, "tests", "swelive_spec.json"), "w", encoding="utf-8") as fh:
    json.dump(spec, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

# ---------------------------------------------------------------- task.toml
task_toml = '''# ============================================================
# 标准 Harbor Task 配置
# 目标 Schema: 1.3（若平台书面确认升级，以冻结版本为准）
#
# 身份三元组：
#   task_id    = %s
#   task_version = %s
#   task_hash  = %s
# 必须与 tests/swelive_spec.json 及
# extras/metadata/manifest.json 完全一致。
#
# 任何影响 题面 / 环境 / Solution / Tests / 判分 的修改，必须升级 version
# 并重新执行受影响的验收环节。
# ============================================================

version = "%s"

[metadata]
author_name = "wfflab"
tags = ["coding", "windows", "windows-bench"]

[agent]
# 规范：单次端到端评测原则上 <= 12 小时（43200s）。本题用例都是纯逻辑的
# 确定性用例，3 小时足够。
timeout_sec = 10800.0

[verifier]
timeout_sec = 3600.0

[environment]
# 镜像由 task-build 在构建期生成；此处声明构建后的引用名。
# 不可变身份另存于 _index/EXTERNAL_IMAGES.json 的 image_digest 字段。
docker_image = "%s"
build_timeout_sec = 3600.0
cpus = 4
memory = "8G"
storage = "20G"
''' % (TASK_ID, VERSION, task_hash, VERSION, WREF)
with open(os.path.join(ROOT, "task.toml"), "w", encoding="utf-8") as fh:
    fh.write(task_toml)

# ---------------------------------------------------------------- platform_import
platform = {
    "instance_id": TASK_ID,
    "task_version": VERSION,
    "task_hash": task_hash,
    "docker_image": WREF,
    "image_digest": None,
    "instruction_file": TASK_ID + "/instruction.md",
    "assets_path": TASK_ID,
    "harness": "standalone test.ps1 + grade.py（Harbor schema 1.3）",
    "tags": ["coding", "windows", "windows-bench"],
    "primary_direction": "系统管理",
    "difficulty": "L4",
    "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以同目录（%s/）中"
              "通过冻结 Schema 校验的内容为准。两者引用同一身份三元组。" % TASK_ID),
}
with open(os.path.join(ROOT, "platform_import.json"), "w", encoding="utf-8") as fh:
    json.dump(platform, fh, indent=2, ensure_ascii=False)
    fh.write("\n")

# ---------------------------------------------------------------- manifest
manifest = {
    "_comment": "身份三元组与制品哈希（规范 3.5-⑥）",
    "_identity": ("唯一验收身份 = task_id + task_version + task_hash。task.toml / "
                  "tests/swelive_spec.json / platform_import.json / 本文件必须完全一致。"),
    "_task_hash_definition": ("sha256( 'task_id=' + id + '\\n' + 'task_version=' + v + '\\n' + "
                              "'instruction_md_sha256=' + h + '\\n' + 'test_patch_sha256=' + h + '\\n' + "
                              "'oracle_patch_sha256=' + h + '\\n' + 'dockerfile_sha256=' + h )。"
                              "逐行以 \\n 连接，**末行不带换行**。刻意不含 task.toml 自身，"
                              "以便 task_hash 可回写进 task.toml。"),
    "task_id": TASK_ID,
    "task_version": VERSION,
    "task_hash": task_hash,
    "source_commit": commit,
    "base_commit": commit,
    "image_ref": WREF,
    "image_digest": None,
    "image_digest_status": "PENDING_BUILD",
    "artifacts": {
        "task_toml_sha256": sha256(os.path.join(ROOT, "task.toml")),
        "instruction_md_sha256": instr,
        "test_patch_sha256": tp,
        "oracle_patch_sha256": orac,
        "spec_sha256": sha256(os.path.join(ROOT, "tests", "swelive_spec.json")),
        "dockerfile_sha256": dock,
        "grade_py_sha256": sha256(os.path.join(ROOT, "tests", "grade.py")),
        "test_ps1_sha256": sha256(os.path.join(ROOT, "tests", "test.ps1")),
    },
    "windows_target": {
        "version": "Windows Server 2022",
        "edition": "Datacenter",
        "arch": "x64",
        "locale": "en-US",
    },
    "frozen_baseline": {
        "harbor_schema": "1.3",
        "harness": "standalone test.ps1 + grade.py（本题不依赖 harbor-rewardkit）",
        "models": ["Qwen3.8-Max-0902", "Opus 5", "GLM-5.3", "Kimi K3"],
        "frozen_at": "2026-10-04",
        "tool_permissions": "容器内全权限（管理员），Agent 仅可写 C:\\testbed",
        "network_policy": "运行期 air-gapped；构建期允许拉取锁定版本的 Python/pytest",
        "sampling": {"temperature": 0.0, "top_p": 1.0},
        "budget": {"agent_timeout_sec": 10800, "verifier_timeout_sec": 3600},
        "test_runtime": {"python": "3.12.9", "pytest": "8.3.5", "pytest_json_report": "1.5.0"},
    },
}
os.makedirs(os.path.join(ROOT, "extras", "metadata"), exist_ok=True)
with open(os.path.join(ROOT, "extras", "metadata", "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print("meta written")
