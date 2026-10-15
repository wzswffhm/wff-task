#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_package.py — Windows 专项 Coding Bench 题包校验器（现行形态对齐版）

## 口径优先级（重要）

**冲突时一律以随包甲方脚本 `_reference/windows-harbor-qc/scripts/` 的行为为准**：

| 甲方脚本 | 本校验器对应的检查 |
|---|---|
| `inspect_delivery.py: inspect_delivery` | 顶层件、`task.toml` 身份/镜像、`required_testcases.json` 条数、`adapter.toml` |
| `run_qc.py: static_check` | `environment/` 七件、`tests/` 六件、`docker_image`、`judge.toml` ↔ `rubric.json` 哈希 |
| `validate_model_gate.py` / `validate_model_jobs.py` | `jobs/` 12 个 job（`REQUIRED_COUNTS={"qwen":3,"opus":3}` + Oracle×3 + NOP×3） |

本脚本只是**本地零成本预检**（甲方自检是阶段 4.5 的硬门，不能替代）。
凡甲方工具不检查、只属于**历史形态**的项（旧 `outside_harbor-assets/` 嵌套式、
`extras/`、`platform_import.json`、`swelive_spec.json`、`_index/`、GLM/Kimi 必需、
`[agent]`/`[verifier]` 段落），一律**不再判 FAIL**：现行 5 个生效包都不带它们。

## 现行形态（唯一事实来源 = `harbor-windows/` 下的生效题包）

```
<task-id>-v<版本>-delivery/
├── task.toml            # 必须含顶层 docker_image，且与 environment/Dockerfile 的 FROM 逐字一致
├── instruction.md
├── source.json
├── environment/         # 七件：adapter.toml Dockerfile prepare.ps1 validate_environment.ps1 run.ps1 restore.ps1 cleanup.ps1
├── tests/               # 六件：test.ps1 run_tests.ps1 aggregate_results.ps1 judge.toml rubric.json required_testcases.json
├── solution/            # README.md + solve.ps1|solve.bat（+ reference/**）
├── verifier/            # 判分侧资产（负访问探针、rubric.conditions.json 等）
├── jobs/                # 12 个 job：qwen×3 + opus×3 + Oracle×3 + NOP×3
└── metadata/            # windows_mechanism.json（F1–F6 门禁产物）
```

用法：
    python validate_package.py --package <题包根目录>
    python validate_package.py --package <题包根目录> --json report.json
    python validate_package.py --task-dir <单个题包目录>

退出码：
    0  全部通过（可能含 FLAG 警告）
    1  存在 FAIL（不满足验收）
    2  参数或读取错误
"""

import argparse
import hashlib
import json
import os
import re
import sys

# ---------------------------------------------------------------- 常量

# 标准 Harbor 五件套（规范 5.1）—— 与 inspect_delivery.TASK_ROOT_ITEMS 一致
REQUIRED_TASK_FILES = ["task.toml", "instruction.md"]
REQUIRED_TASK_DIRS = ["environment", "solution", "tests"]

# 甲方 run_qc.static_check 的 environment/ 七件
REQUIRED_ENV_FILES = ["adapter.toml", "Dockerfile", "prepare.ps1", "validate_environment.ps1",
                      "run.ps1", "restore.ps1", "cleanup.ps1"]

# 甲方 run_qc.static_check 的 tests/ 六件
REQUIRED_TESTS_FILES = ["test.ps1", "run_tests.ps1", "aggregate_results.ps1",
                        "judge.toml", "rubric.json", "required_testcases.json"]

# 甲方 validate_model_jobs：qwen/opus 各 3，外加 Oracle×3 + NOP×3
REQUIRED_MODEL_COUNTS = {"qwen": 3, "opus": 3}
REQUIRED_ORACLE_JOBS = 3
REQUIRED_NOP_JOBS = 3

# required_testcases.json 条数区间（甲方：<5 判 FAIL；>27 只告警）
MIN_TESTCASES = 5
MAX_TESTCASES = 27

# 严禁出现在 Agent 可见环境中的内容
FORBIDDEN_IN_ENV = ["solution", "oracle", "golden", "answer", "reward"]

# 已知的题面泄漏信号
LEAK_PATTERNS = [
    (re.compile(r"golden[_\s-]?patch", re.I), "提到 Golden Patch"),
    (re.compile(r"oracle[_\s-]?patch", re.I), "提到 Oracle Patch"),
    (re.compile(r"hidden[_\s-]?test", re.I), "提到隐藏测试"),
    (re.compile(r"FAIL_TO_PASS|PASS_TO_PASS", re.I), "提到 F2P/P2P 标识"),
    (re.compile(r"reward(\.json|\.txt)?\b", re.I), "提到 Reward 产物"),
]

INVALID_MARKER = re.compile(r"===SWELIVE_INVALID\s+([^=]+)===")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, category, msg, detail=""):
        self.items.append({"level": level, "category": category, "msg": msg, "detail": detail})

    def ok(self, category, msg, detail=""):
        self.add("PASS", category, msg, detail)

    def fail(self, category, msg, detail=""):
        self.add("FAIL", category, msg, detail)

    def flag(self, category, msg, detail=""):
        self.add("FLAG", category, msg, detail)

    def counts(self):
        c = {"PASS": 0, "FAIL": 0, "FLAG": 0}
        for i in self.items:
            c[i["level"]] += 1
        return c

    def render(self):
        lines = []
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "FLAG": "[FLAG]"}
        for i in self.items:
            lines.append(f"{icon[i['level']]} [{i['category']}] {i['msg']}")
            if i["detail"]:
                for ln in str(i["detail"]).splitlines():
                    lines.append(f"         {ln}")
        c = self.counts()
        lines.append("")
        lines.append(f"总计: PASS={c['PASS']} FAIL={c['FAIL']} FLAG={c['FLAG']}")
        return "\n".join(lines)


# ---------------------------------------------------------------- 现行形态检查

def check_structure(task_dir, r):
    """五件套 + solution 入口（inspect_delivery.TASK_ROOT_ITEMS / run_qc.static_check）。"""
    missing = []
    for f in REQUIRED_TASK_FILES:
        if not os.path.isfile(os.path.join(task_dir, f)):
            missing.append(f)
    for d in REQUIRED_TASK_DIRS:
        if not os.path.isdir(os.path.join(task_dir, d)):
            missing.append(d + "/")
    if missing:
        r.fail("结构", f"缺失标准 Harbor 必需项: {', '.join(missing)}",
               "五件套 = task.toml / instruction.md / environment/ / solution/ / tests/")
    else:
        r.ok("结构", "标准 Harbor 五件套齐全")

    sol = os.path.join(task_dir, "solution")
    if os.path.isdir(sol):
        entries = [f for f in ("solve.ps1", "solve.bat") if os.path.isfile(os.path.join(sol, f))]
        if entries:
            r.ok("结构", f"solution/ 具备标准入口: {', '.join(entries)}")
        else:
            r.fail("结构", "solution/ 缺 solve.ps1 / solve.bat 入口",
                   "甲方 run_qc.static_check: solution must provide solve.ps1 or solve.bat")


def check_env_required(task_dir, r):
    """environment/ 七件（甲方 run_qc.static_check）。"""
    env = os.path.join(task_dir, "environment")
    if not os.path.isdir(env):
        return
    missing = [f for f in REQUIRED_ENV_FILES if not os.path.isfile(os.path.join(env, f))]
    if missing:
        r.fail("environment", f"缺 environment/ 必备件: {', '.join(missing)}",
               f"甲方要求七件: {' '.join(REQUIRED_ENV_FILES)}")
    else:
        r.ok("environment", "environment/ 七件齐全")

    adapter = os.path.join(env, "adapter.toml")
    if os.path.isfile(adapter):
        try:
            import tomllib
            with open(adapter, "rb") as fh:
                data = tomllib.load(fh)
            keys = ("prepare", "validate", "run", "restore", "cleanup", "workspace")
            missing_keys = [k for k in keys if not data.get(k)]
            if missing_keys:
                r.fail("environment", f"adapter.toml 缺扁平 key: {', '.join(missing_keys)}",
                       "甲方 inspect_delivery 读的是扁平 key（不是 [prepare] 之类的表）")
            else:
                unresolved = [k for k in keys
                              if not os.path.exists(os.path.join(env, str(data[k])))]
                if unresolved:
                    r.fail("environment", f"adapter.toml 指向的文件缺失: {', '.join(unresolved)}")
                else:
                    r.ok("environment", "adapter.toml 可被 TOML 解析，六个扁平 key 均已解析到真实文件")
        except Exception as exc:  # noqa: BLE001
            r.fail("environment", f"environment/adapter.toml 无法解析: {type(exc).__name__}: {exc}",
                   "典型坑：同时写扁平 key 与同名 [table]，TOML 会直接报 Cannot overwrite a value")


def check_tests_required(task_dir, r):
    """tests/ 六件 + INVALID 区分 + 二值判分（甲方 run_qc.static_check）。"""
    tests = os.path.join(task_dir, "tests")
    if not os.path.isdir(tests):
        return
    files = sorted(os.listdir(tests))
    r.ok("tests", f"tests/ 文件: {', '.join(files)}")

    missing = [f for f in REQUIRED_TESTS_FILES if f not in files]
    if missing:
        r.fail("tests", f"缺 tests/ 必备件: {', '.join(missing)}",
               f"甲方要求六件: {' '.join(REQUIRED_TESTS_FILES)}")
    else:
        r.ok("tests", "tests/ 六件齐全（含甲方必备的 judge.toml / rubric.json / required_testcases.json）")

    entry = None
    for cand in ("test.ps1", "test.sh", "test.py"):
        if cand in files:
            entry = os.path.join(tests, cand)
            break
    if not entry:
        r.fail("tests", "未找到验证入口（test.ps1 / test.sh / test.py）")
        return
    txt = open(entry, encoding="utf-8", errors="replace").read()

    if INVALID_MARKER.search(txt) or "INVALID" in txt.upper():
        r.ok("INVALID 区分", "验证入口具备 INVALID 标记能力")
    else:
        r.fail("INVALID 区分", "验证入口未区分 INVALID（基础设施故障不得伪装成模型 0 分）",
               "存在 required 未执行/缺失/SKIP 或基础设施异常须标为 INVALID")

    has_binary = bool(re.search(r"(reward|score)\s*=\s*(1|1\.0|0|0\.0)\b", txt)) or \
                 "reward.txt" in txt or "reward.json" in txt
    if has_binary:
        r.ok("二值判分", "存在二值评分产物写出")
    else:
        r.flag("二值判分", "未在验证入口检测到 reward 产物写出；确认评分由聚合器完成")

    # 现行形态：judge.toml 的 source_sha256 必须等于 rubric.json 的**实字节** sha256
    judge_p = os.path.join(tests, "judge.toml")
    rubric_p = os.path.join(tests, "rubric.json")
    if os.path.isfile(judge_p) and os.path.isfile(rubric_p):
        try:
            import tomllib
            with open(judge_p, "rb") as fh:
                judge = tomllib.load(fh)
            declared = judge.get("source_sha256") or judge.get("rubric_sha256")
            actual = sha256(rubric_p)
            if not declared:
                r.fail("判分配置", "judge.toml 缺 source_sha256",
                       "甲方静态门：judge.toml rubric hash does not match rubric.json")
            elif str(declared).lower() != actual:
                r.fail("判分配置", "judge.toml 的 source_sha256 与 rubric.json 实字节 sha256 不一致",
                       f"judge.toml : {declared}\nrubric.json: {actual}")
            else:
                r.ok("判分配置", f"judge.toml.source_sha256 与 rubric.json 实字节 sha256 一致 ({actual[:12]}…)")
        except Exception as exc:  # noqa: BLE001
            r.fail("判分配置", f"judge.toml 解析失败: {type(exc).__name__}: {exc}")

    # rubric.json 必须可解析为对象，且 test_ids 覆盖 required_testcases.json
    req_p = os.path.join(tests, "required_testcases.json")
    if os.path.isfile(rubric_p) and os.path.isfile(req_p):
        try:
            rubric = json.load(open(rubric_p, encoding="utf-8"))
            rows = json.load(open(req_p, encoding="utf-8"))
            declared_ids = set()
            for item in rubric.get("items") or []:
                declared_ids.update(item.get("test_ids") or [])
            actual_ids = {str(row.get("id")) for row in rows if isinstance(row, dict)}
            undeclared = sorted(actual_ids - declared_ids)
            if undeclared:
                r.fail("判分配置", f"required_testcases.json 有 {len(undeclared)} 条未在 rubric.json 声明",
                       ", ".join(undeclared[:8]))
            else:
                r.ok("判分配置", f"rubric.json 覆盖全部 {len(actual_ids)} 条 required testcase")
        except Exception as exc:  # noqa: BLE001
            r.fail("判分配置", f"rubric.json / required_testcases.json 读取失败: {exc}")


def check_required_testcases(task_dir, r):
    """required_testcases.json：顶层数组、5–27 条、id 唯一、同时含 F2P 与 P2P。"""
    p = os.path.join(task_dir, "tests", "required_testcases.json")
    if not os.path.isfile(p):
        return
    try:
        data = json.load(open(p, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        r.fail("required_testcases", f"解析失败: {exc}")
        return
    if not isinstance(data, list):
        r.fail("required_testcases", "顶层必须是数组（甲方：must be a list）")
        return
    n = len(data)
    if n < MIN_TESTCASES:
        r.fail("required_testcases", f"只有 {n} 条，少于甲方要求的 {MIN_TESTCASES} 条")
    elif n > MAX_TESTCASES:
        r.flag("required_testcases", f"有 {n} 条，超过 {MAX_TESTCASES} 条需人工复核范围",
               "甲方口径：>27 只告警，本身不阻塞 QC")
    else:
        r.ok("required_testcases", f"{n} 条（{MIN_TESTCASES}–{MAX_TESTCASES} 区间内）")

    ids, groups = [], {}
    bad = []
    for row in data:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or \
                row.get("group") not in ("F2P", "P2P"):
            bad.append(str(row)[:60])
            continue
        ids.append(row["id"])
        groups[row["id"]] = row["group"]
    if bad:
        r.fail("required_testcases", f"{len(bad)} 条缺少 id 或 group 不是 F2P/P2P", "\n".join(bad[:5]))
    if len(ids) != len(set(ids)):
        r.fail("required_testcases", "required testcase id 有重复")
    if groups and (not any(g == "F2P" for g in groups.values())
                   or not any(g == "P2P" for g in groups.values())):
        r.fail("required_testcases", "必须同时含 F2P 与 P2P")
    elif groups:
        f2p = sum(1 for g in groups.values() if g == "F2P")
        r.ok("required_testcases", f"F2P={f2p} P2P={len(groups) - f2p}")


def check_task_toml(task_dir, r, expect_schema=None):
    """task.toml 关键字段（含现行硬性 docker_image 口径）。"""
    p = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(p):
        return None
    txt = open(p, encoding="utf-8", errors="replace").read()

    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', txt, re.M)
    ver = None
    if not m:
        r.fail("task.toml", "缺少 version 字段")
    else:
        ver = m.group(1)
        r.ok("task.toml", f"version = {ver}")

    # 目标 Schema 与题目 version 是两个口径：前者来自顶部注释的显式声明。
    ms = re.search(r'目标\s*Schema\s*[:：]\s*([0-9.]+)', txt)
    if ms:
        schema = ms.group(1)
        if expect_schema and schema != expect_schema:
            r.flag("task.toml", f"声明目标 Schema '{schema}' 与期望 '{expect_schema}' 不一致")
        else:
            r.ok("task.toml", f"目标 Schema = {schema}（与期望一致）")
    elif expect_schema and ver:
        r.flag("task.toml",
               f"task.toml 未声明「目标 Schema」；其 version='{ver}' 是题目版本，"
               f"与 --schema-version '{expect_schema}' 不是同一口径，无法直接比较",
               "建议在 task.toml 顶部注释显式声明「目标 Schema: X.Y」以便校验")

    # 甲方 inspect_delivery 读的身份字段
    tid = re.search(r'(?m)^\s*task_id\s*=\s*"([^"]+)"', txt)
    if tid:
        r.ok("task.toml", f"task_id = {tid.group(1)}")
    else:
        r.fail("task.toml", "缺 task_id（[metadata].task_id 或顶层 task_id）")

    # 现行硬性口径：task.toml **必须**写 docker_image，且与 Dockerfile 的 FROM 逐字一致。
    # 依据：甲方 run_qc.static_check 与 inspect_delivery 都把它当必需项
    #   （缺则 "task.toml has no docker_image" / "Task has no pinned Docker image"）。
    img = re.search(r'(?m)^\s*docker_image\s*=\s*"([^"]+)"', txt)
    df_p = os.path.join(task_dir, "environment", "Dockerfile")
    df_from = None
    if os.path.isfile(df_p):
        fm = re.search(r"(?mi)^\s*FROM\s+(\S+)",
                       open(df_p, encoding="utf-8", errors="replace").read())
        df_from = fm.group(1) if fm else None
    if not img:
        r.fail("task.toml", "task.toml 缺顶层 docker_image",
               "甲方必备项：缺则 run_qc 报 'task.toml has no docker_image'、"
               "inspect_delivery 报 'Task has no pinned Docker image'")
    else:
        value = img.group(1).strip()
        if value.casefold() == "latest" or value.casefold().endswith(":latest"):
            r.fail("task.toml", "docker_image 不得使用浮动 latest tag", value)
        elif "@sha256:" not in value:
            r.fail("task.toml", "docker_image 未 pin 到不可变 digest（缺 @sha256:）", value)
        elif df_from is None:
            r.flag("task.toml", "environment/Dockerfile 缺 FROM，无法核对镜像一致性")
        elif value != df_from:
            r.fail("task.toml", "docker_image 与 environment/Dockerfile 的 FROM 不一致",
                   f"task.toml : {value}\nDockerfile: {df_from}")
        else:
            r.ok("task.toml", f"docker_image 与 Dockerfile FROM 逐字一致，已 pin digest ({value[-18:]})")

    # 12 小时上限
    am = re.search(r"\[agent\][^\[]*?timeout_sec\s*=\s*([\d.]+)", txt, re.S)
    if am:
        secs = float(am.group(1))
        if secs > 43200:
            r.flag("task.toml", f"agent.timeout_sec = {secs:.0f}s ({secs/3600:.1f}h) 超过 12 小时上限")
        else:
            r.ok("task.toml", f"agent.timeout_sec = {secs/3600:.1f}h（≤12h）")
    return txt


def check_jobs(task_dir, r):
    """jobs/ 结构：12 个 job = qwen×3 + opus×3 + Oracle×3 + NOP×3。

    判据与甲方 `validate_model_jobs.validate_jobs` 一致：job 目录须含 `result.json`；
    目录名按 `model-<alias>-N` / `ctl-oracle-N` / `ctl-nop-N` 归类。
    """
    jobs = os.path.join(task_dir, "jobs")
    if not os.path.isdir(jobs):
        r.fail("jobs", "缺 jobs/ 目录",
               "甲方 validate_model_jobs 要求 12 个 job（qwen×3 + opus×3 + Oracle×3 + NOP×3）；"
               "尚未跑分时属真实缺件，跑分后补齐再交付")
        return
    job_dirs = sorted(d for d in os.listdir(jobs)
                      if os.path.isdir(os.path.join(jobs, d))
                      and os.path.isfile(os.path.join(jobs, d, "result.json")))
    expected = sum(REQUIRED_MODEL_COUNTS.values()) + REQUIRED_ORACLE_JOBS + REQUIRED_NOP_JOBS

    counts = {"qwen": 0, "opus": 0, "oracle": 0, "nop": 0, "unknown": []}
    for name in job_dirs:
        low = name.casefold()
        if "oracle" in low:
            counts["oracle"] += 1
        elif "nop" in low:
            counts["nop"] += 1
        elif "qwen" in low:
            counts["qwen"] += 1
        elif "opus" in low:
            counts["opus"] += 1
        else:
            counts["unknown"].append(name)

    if len(job_dirs) != expected:
        r.fail("jobs", f"jobs/ 有 {len(job_dirs)} 个 job，甲方要求恰好 {expected} 个",
               f"已识别: qwen={counts['qwen']} opus={counts['opus']} "
               f"oracle={counts['oracle']} nop={counts['nop']}")
    else:
        r.ok("jobs", f"jobs/ 恰好 {expected} 个 job")

    for model, want in REQUIRED_MODEL_COUNTS.items():
        if counts[model] != want:
            r.fail("jobs", f"{model} 轮有 {counts[model]} 个 job，甲方要求 {want} 个")
    for agent, want in (("oracle", REQUIRED_ORACLE_JOBS), ("nop", REQUIRED_NOP_JOBS)):
        if counts[agent] != want:
            r.fail("jobs", f"{agent} 轮有 {counts[agent]} 个 job，甲方要求 {want} 个")
    if counts["unknown"]:
        r.flag("jobs", f"无法归类的 job 目录: {', '.join(counts['unknown'][:6])}")
    if counts["qwen"] == 3 and counts["opus"] == 3 and \
            counts["oracle"] == 3 and counts["nop"] == 3:
        r.ok("jobs", "12 个 job 分布正确（Qwen×3 + Opus×3 + Oracle×3 + NOP×3）")

    # 必备件（甲方 COMMON_FILES + 两个控制轮的专属文件）
    common = ["config.json", "lock.json", "result.json", "trial.log", "artifacts/manifest.json",
              "verifier/result.json", "verifier/reward.txt", "verifier/test-stdout.txt",
              "verifier/verifier.log"]
    model_files = ["agent/model-result.json", "agent/trajectory.jsonl"]
    oracle_files = ["agent/oracle.txt", "agent/qc-oracle-application.json"]
    missing = []
    for name in job_dirs:
        base = os.path.join(jobs, name)
        low = name.casefold()
        need = list(common)
        if "oracle" in low:
            need += oracle_files
        elif "nop" not in low:
            need += model_files
        miss = [f for f in need if not os.path.isfile(os.path.join(base, f))]
        if miss:
            missing.append(f"{name}: {', '.join(miss)}")
    if missing:
        r.flag("jobs", f"{len(missing)} 个 job 缺必备文件（以甲方 report.md 报错为准）",
               "\n".join(missing[:6]))
    elif job_dirs:
        r.ok("jobs", "全部 job 的必备文件齐全")


def check_identity_harbor(task_dir, r):
    """身份字段 + Harbor dirhash 可复算（对齐 inspect_delivery）。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        here = os.path.dirname(os.path.abspath(__file__))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_qc_inspect_delivery",
            os.path.join(here, "..", "..", "..", "_reference", "windows-harbor-qc",
                         "scripts", "inspect_delivery.py"))
        # 随包甲方脚本缺失时静默跳过（本仓库结构可能不同）
        if spec is None or not os.path.isfile(spec.origin or ""):
            raise FileNotFoundError("bundled inspect_delivery.py not found")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        info = mod.inspect_delivery(__import__("pathlib").Path(task_dir))
        ident = info.get("task") or {}
        for field in ("task_id", "task_version", "task_hash", "harbor_task_checksum"):
            if not ident.get(field):
                r.fail("身份", f"Task has no {field}")
        if ident.get("task_id"):
            r.ok("身份", f"task_id={ident['task_id']} task_version={ident.get('task_version')} "
                         f"dirhash={str(ident.get('harbor_task_checksum'))[:12]}…")
        rc = os.path.join(task_dir, "tests", "required_testcases.json")
        if os.path.isfile(rc) and info.get("testcase_count") is not None:
            r.ok("身份", f"甲方口径 testcase_count = {info['testcase_count']}")
    except Exception as exc:  # noqa: BLE001
        r.flag("身份", f"未使用随包甲方 inspect_delivery.py 复算身份（{type(exc).__name__}），"
                       f"仅做本地字段检查")


def check_instruction_no_leak(task_dir, r):
    """instruction.md 是否泄漏解法/答案。"""
    p = os.path.join(task_dir, "instruction.md")
    if not os.path.isfile(p):
        return
    txt = open(p, encoding="utf-8", errors="replace").read()
    hits = []
    for rx, desc in LEAK_PATTERNS:
        for m in rx.finditer(txt):
            s = max(0, m.start() - 40)
            hits.append(f"{desc}: ...{txt[s:m.end()+40].strip()}...")
    if hits:
        r.fail("题面泄漏", f"instruction.md 命中 {len(hits)} 处泄漏信号", "\n".join(hits[:8]))
    else:
        r.ok("题面泄漏", "instruction.md 未命中已知泄漏信号")

    if len(txt.strip()) < 80:
        r.flag("题面质量", f"instruction.md 仅 {len(txt.strip())} 字符，可能是薄题")
    else:
        r.ok("题面质量", f"instruction.md {len(txt.strip())} 字符")


def check_env_no_solution(task_dir, r):
    """environment/ 是否混入 Solution / 隐藏测试。"""
    env = os.path.join(task_dir, "environment")
    if not os.path.isdir(env):
        return
    bad = []
    for root, dirs, files in os.walk(env):
        for name in files + dirs:
            low = name.lower()
            if any(token in low for token in FORBIDDEN_IN_ENV):
                bad.append(os.path.relpath(os.path.join(root, name), task_dir))
    if bad:
        r.fail("环境泄漏", f"environment/ 内出现疑似 Solution/答案: {', '.join(bad[:10])}")
    else:
        r.ok("环境泄漏", "environment/ 未见 Solution/答案/隐藏测试")


def check_windows_value(task_dir, r, extras_dir=None, allow_legacy_exempt=False):
    """Windows 专属机制门禁 F1–F6（references/12-windows-mechanism-gate.md）。"""
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location(
            "check_windows_mechanism", os.path.join(here, "check_windows_mechanism.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001
        r.flag("Windows机制", f"无法加载 check_windows_mechanism.py，跳过机制门禁: {exc!r}")
        return

    res, summary = mod.check_task(task_dir, extras_dir, allow_legacy_exempt)
    tid = summary.get("task_id") or os.path.basename(os.path.normpath(task_dir))
    if res.valid:
        n = len(summary.get("mechanisms", []))
        r.ok("Windows机制", f"{tid}: Windows 专属机制门禁通过（登记 {n} 条机制，均有题面与 F2P 用例锚点）")
    else:
        r.fail("Windows机制", f"{tid}: Windows 专属机制门禁 FAIL（{len(res.errors)} 条）",
               "\n".join(res.errors[:8]))
    for w in res.warnings:
        r.flag("Windows机制", f"{tid}: {w}")


def check_task(task_dir, r, schema_version=None, extras=None):
    """单个平铺题包的全部现行形态检查。"""
    check_structure(task_dir, r)
    check_task_toml(task_dir, r, schema_version)
    check_instruction_no_leak(task_dir, r)
    check_env_no_solution(task_dir, r)
    check_env_required(task_dir, r)
    check_tests_required(task_dir, r)
    check_required_testcases(task_dir, r)
    check_identity_harbor(task_dir, r)
    check_windows_value(task_dir, r, extras)
    check_jobs(task_dir, r)


def check_flat_package(pkg, r, schema_version, extras=None):
    """平铺布局：pkg 下每个含 task.toml 的子目录 = 一个自包含题包。"""
    tasks = []
    for d in sorted(os.listdir(pkg)):
        full = os.path.join(pkg, d)
        if os.path.isdir(full) and os.path.isfile(os.path.join(full, "task.toml")):
            tasks.append((d, full))

    if not tasks:
        r.fail("模式", f"{pkg} 下未找到任何含 task.toml 的题目录")
        return

    r.ok("模式", f"平铺校验 {len(tasks)} 题（{pkg}）")
    for tid, full in tasks:
        check_task(full, r, schema_version, extras)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(
        description="Windows 专项 Coding Bench 题包校验器（现行形态；冲突时以随包甲方脚本为准）")
    ap.add_argument("--package", help="平铺题包根目录（其下每个含 task.toml 的子目录为一题）")
    ap.add_argument("--task-dir", help="单个题包目录（含 task.toml）")
    ap.add_argument("--extras", help="delivery-extras 目录（门禁产物可能在其 tasks/<id>/metadata/ 下）")
    ap.add_argument("--schema-version", default="1.3", help="期望的 Harbor Schema 版本（默认 1.3）")
    ap.add_argument("--json", help="把结果写入 JSON 文件")
    ap.add_argument("--allow-legacy-exempt", action="store_true",
                    help="允许历史包通过 WINDOWS_MECHANISM_EXEMPT.md 把 F1–F5 降级为 FLAG（F6 不免除）")
    args = ap.parse_args()

    if not args.package and not args.task_dir:
        print("错误: 需指定 --package 或 --task-dir", file=sys.stderr)
        return 2

    r = Report()
    pkg = args.package

    if args.task_dir:
        td = os.path.abspath(args.task_dir)
        if not os.path.isdir(td):
            print(f"错误: 目录不存在 {td}", file=sys.stderr)
            return 2
        r.ok("模式", f"单题校验: {td}")
        check_task(td, r, args.schema_version, args.extras)
    else:
        pkg = os.path.abspath(pkg)
        if not os.path.isdir(pkg):
            print(f"错误: 目录不存在 {pkg}", file=sys.stderr)
            return 2
        check_flat_package(pkg, r, args.schema_version, args.extras)

    print(r.render())
    if args.json:
        c = r.counts()
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": c, "items": r.items}, f, ensure_ascii=False, indent=2)
        print(f"\n报告已写入 {args.json}")
    return 1 if r.counts()["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
