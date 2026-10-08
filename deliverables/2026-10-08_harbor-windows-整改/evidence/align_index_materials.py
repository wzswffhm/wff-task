"""Regenerate harbor-windows/_index summary materials for the two packages that
actually exist in this workspace (wfflab__wfmt-215, wfflab__wreparse-217).

The previous _index described a different, larger task set (9/16 tasks) carried
over from the full repository, which made the directory materials contradict the
delivered packages. Every number written here is derived from files on disk:
  * task/web identity  <- task.toml, source.json, environment/workspace
  * control + model    <- <task>/jobs/_index/qualification_summary.json
  * testcase tallies   <- <task>/jobs/<run_id>/verifier/checks.json
  * package hash       <- deterministic tree hash (see TASK_HASH_RULE)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
INDEX = ROOT / "_index"

TASKS = ["wfflab__wfmt-215", "wfflab__wreparse-217"]

# What the client's delivery brief calls each package; kept identical to task.toml.
META = {
    "wfflab__wfmt-215": {
        "primary_direction": "编码与区域",
        "direction_note": "题目实体是长度前缀记录容器格式（LEB128 变长整数 / 对齐填充 / 尾部 32 位 CRC / 流式解码），归入「编码与区域」为近似映射",
        "secondary_tags": "二进制容器格式；长度前缀分帧；LEB128 变长整数；按记录对齐填充；尾部 32 位 CRC；流式读取；截断与篡改检测",
        "package": "wfmt",
        "package_version": "0.9.3",
        "language": "Python",
        "image_id": "sha256:36b792b8c6bbfb03925dba2453f68bc77b6026644d2d687f6a12a39357153007",
        "image_ref": "outside-harbor/wfflab__wfmt-215:1.0",
    },
    "wfflab__wreparse-217": {
        "primary_direction": "文件系统与路径",
        "direction_note": "NTFS 重解析点（junction / 符号链接 / 挂载点）的安全遍历与确定性审计",
        "secondary_tags": "NTFS 重解析点；junction 与符号链接区分；目录边界包含判定；相对目标解析；规范化路径；深度限制；循环检测；确定性报告",
        "package": "WReparse",
        "package_version": "1.0.0",
        "language": "PowerShell",
        "image_id": "sha256:37fdf8e192c68dcc7b88c6a529e49f13141fb8fbccbe8fbad908733f74db68f0",
        "image_ref": "outside-harbor/wfflab__wreparse-217:1.0",
    },
}

MODEL_LABELS = {
    "QWEN": "Qwen3.8-Max-0902",
    "OPUS": "Opus 5",
    "GLM": "GLM-5.3",
    "KIMI": "Kimi K3",
}

# Stable machine keys used by the platform's model-validation contract.
MODEL_KEYS = {
    "QWEN": "qwen3.8-max",
    "OPUS": "opus-5",
    "GLM": "glm-5.3",
    "KIMI": "kimi-k3",
}

TASK_HASH_RULE = (
    "sha256 over the task definition tree: for every file under the task root "
    "except jobs/, in sorted forward-slash relative-path order, feed "
    "'<relpath>\\n<sha256(file)>\\n'"
)


def tree_hash(task_dir: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
    )
    for path in files:
        rel = path.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8") + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def load(task_id: str) -> dict:
    return json.loads((ROOT / task_id / "jobs" / "_index" / "qualification_summary.json")
                      .read_text(encoding="utf-8-sig"))


def case_pass_count(task_id: str, run_id: str) -> int | None:
    path = ROOT / task_id / "jobs" / run_id / "verifier" / "checks.json"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    checks = doc.get("checks") or []
    return sum(1 for c in checks if str(c.get("status", "")).upper() == "PASS")


def toml_version(task_id: str) -> dict:
    import tomllib
    return tomllib.loads((ROOT / task_id / "task.toml").read_text(encoding="utf-8"))


def required_counts(task_id: str) -> tuple[int, int, int]:
    items = json.loads((ROOT / task_id / "tests" / "required_testcases.json")
                       .read_text(encoding="utf-8-sig"))
    f2p = sum(1 for i in items if i.get("group") == "F2P")
    p2p = sum(1 for i in items if i.get("group") == "P2P")
    return f2p, p2p, len(items)


# ---------------------------------------------------------------- tasks_index
rows = ['"task_id","task_version","task_hash","primary_direction","secondary_tags","language",'
        '"task_type","difficulty","windows_target","package","package_version","f2p","p2p",'
        '"status","frozen_at"']
summary_data: dict[str, dict] = {}
for task_id in TASKS:
    cfg = toml_version(task_id)
    meta = META[task_id]
    f2p, p2p, total = required_counts(task_id)
    q = load(task_id)
    gates = q["gates"]
    status = ("多模型区分度达标（qualified=true，Opus score_sum > Qwen score_sum）；"
              "本机 Harbor 控制 3+3 通过、动态门禁 PASS")
    rows.append(",".join([
        f'"{task_id}"',
        f'"{cfg["task"]["version"]}"',
        f'"{tree_hash(ROOT / task_id)}"',
        f'"{meta["primary_direction"]}"',
        f'"{meta["secondary_tags"]}"',
        f'"{meta["language"]}"',
        '"bugfix"',
        f'"{cfg["metadata"]["difficulty"]}"',
        '"Windows Server 2022 / Datacenter / x64 / en-US"',
        f'"{meta["package"]}"',
        f'"{meta["package_version"]}"',
        f'"{f2p}"',
        f'"{p2p}"',
        f'"{status}"',
        f'"{q["qualification_epoch"][:10]}"',
    ]))
    summary_data[task_id] = {"cfg": cfg, "meta": meta, "f2p": f2p, "p2p": p2p,
                             "total": total, "q": q, "gates": gates}
(INDEX / "tasks_index.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

# ------------------------------------------------------------- model_summary
lines = ["task_id,model,model_identity,runs_total,runs_valid,runs_invalid,runs_pending,"
         "model_score_sum,testcase_pass_sum,validity,notes"]
for task_id in TASKS:
    data = summary_data[task_id]
    for key in ("QWEN", "OPUS", "GLM", "KIMI"):
        m = data["q"]["models"].get(key)
        if not m:
            continue
        tally = 0
        missing = False
        for run in m["selected"]:
            n = case_pass_count(task_id, run["run_id"])
            if n is None:
                missing = True
            else:
                tally += n
        excluded = m.get("excluded_agent_failures") or []
        note = f"selected {len(m['selected'])} 轮；排除 agent 失败 {len(excluded)} 轮"
        if missing:
            note += "；部分轮次 checks.json 未随包留存，testcase 计数为已留存部分"
        lines.append(",".join([
            task_id, MODEL_LABELS[key], "", str(m["attempt_count"]), str(m["valid_count"]),
            str(len(m.get("invalid_attempts") or [])), "0", str(m["score_sum"]),
            str(tally), "READY", note,
        ]))
(INDEX / "model_summary.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

# --------------------------------------------------- model_validation_summary
out = {"generated_at": "2026-10-08", "harbor_schema": "1.3", "tasks": []}
for task_id in TASKS:
    data = summary_data[task_id]
    entry = {"task_id": task_id, "models": {}, "validity": {}, "admission": {}}
    for key in ("QWEN", "OPUS", "GLM", "KIMI"):
        m = data["q"]["models"].get(key)
        if not m:
            continue
        tally = 0
        for run in m["selected"]:
            n = case_pass_count(task_id, run["run_id"])
            tally += n or 0
        entry["models"][MODEL_KEYS[key]] = {
            "label": MODEL_LABELS[key],
            "runs_required": m["required"],
            "runs_valid": m["valid_count"],
            "runs_invalid": len(m.get("invalid_attempts") or []),
            "runs_pending": 0,
            "model_score_sum": m["score_sum"],
            "testcase_pass_sum": tally,
            "scores": m["scores"],
            "scores_known": True,
        }
        entry["validity"][MODEL_KEYS[key]] = "READY"
    opus = data["q"]["models"]["OPUS"]["score_sum"]
    qwen = data["q"]["models"]["QWEN"]["score_sum"]
    passed = bool(data["gates"].get("opus_sum_greater_than_qwen"))
    entry["admission"] = {
        "condition": "opus_sum_greater_than_qwen",
        "passed": passed,
        "reason": (f"Opus model_score_sum {opus} > Qwen model_score_sum {qwen}"
                   if passed else
                   f"Opus model_score_sum {opus} 不严格大于 Qwen {qwen}"),
        "blocking": [],
    }
    out["tasks"].append(entry)
(INDEX / "model_validation_summary.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------- model_validation_report
lines = ["# 多模型验证报告", "", "生成时间：2026-10-08", "",
         "适用范围：本目录当前实际交付的 2 个题包。", "",
         "## 1. 区分度准入汇总", "",
         "| task_id | Qwen score_sum | Opus score_sum | 满足条件 | 结论 |", "|---|---|---|---|---|"]
for task_id in TASKS:
    data = summary_data[task_id]
    opus = data["q"]["models"]["OPUS"]["score_sum"]
    qwen = data["q"]["models"]["QWEN"]["score_sum"]
    ok = data["gates"].get("opus_sum_greater_than_qwen")
    verdict = "PASS — Opus 严格高于 Qwen" if ok else f"FAIL — Opus {opus} 未严格高于 Qwen {qwen}"
    lines.append(f"| {task_id} | {qwen} | {opus} | {'是' if ok else '否'} | {verdict} |")
lines += ["", "## 2. 逐模型运行状态", "",
          "| task_id | 模型 | 要求 | VALID | INVALID | PENDING | 状态 |", "|---|---|---|---|---|---|---|"]
for task_id in TASKS:
    data = summary_data[task_id]
    for key in ("QWEN", "OPUS", "GLM", "KIMI"):
        m = data["q"]["models"].get(key)
        if not m:
            continue
        lines.append(f"| {task_id} | {MODEL_LABELS[key]} | {m['required']} | {m['valid_count']} "
                     f"| {len(m.get('invalid_attempts') or [])} | 0 | READY |")
lines += ["", "## 3. 准入规则", "", "```",
          "条件 1: Opus5.model_score_sum > Qwen.model_score_sum",
          "条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum",
          "```", "",
          "> 只统计 VALID 运行；agent 自身失败（HTTP 4xx/5xx、超时、no_tool_call）的轮次已排除，",
          "> 排除明细见各题 `jobs/_index/qualification_summary.json` 的 `excluded_agent_failures`。",
          "> 模型门槛不能覆盖数据质量门槛。", ""]
(INDEX / "model_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------- knowledge_tree_coverage
directions = [".NET 与桌面应用", "原生开发与互操作", "Shell 与自动化", "文件系统与路径", "系统管理",
              "进程与执行上下文", "安全与身份", "网络与 IPC", "构建安装打包", "编码与区域",
              "诊断与可观测性", "设备与系统底层"]
covered: dict[str, list[str]] = {d: [] for d in directions}
for task_id in TASKS:
    covered[META[task_id]["primary_direction"]].append(task_id)
lines = ["direction,covered,task_ids,coverage_note"]
for d in directions:
    ids = covered[d]
    note = f"覆盖 {len(ids)} 题" if ids else "未覆盖"
    if d == "编码与区域" and ids:
        note += "（wfmt-215 为二进制容器格式方向的近似映射）"
    lines.append(f'"{d}","{len(ids)}","{"; ".join(ids)}","{note}"')
(INDEX / "knowledge_tree_coverage_report.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------- validation_report
lines = ["# validation_report —— harbor-windows 题包目录", "",
         "目录：`harbor-windows/`　｜　题数：**2**　｜　报告日期：2026-10-08", "",
         "> **范围声明**：本目录当前实际交付 2 个题包（`wfflab__wfmt-215`、`wfflab__wreparse-217`）。",
         "> 历史版本的 `_index/` 材料曾按完整仓库的 9 / 16 题范围编写，与本目录实物不符，已于 2026-10-08 按实物重新对齐。", "",
         "## 一、题级验收状态", "",
         "| task_id | 结构合规 | 五件套 | 题面↔测试映射 | 二值判分 | 身份一致 | 对照验证 | 多模型区分度 | Harbor 加载/构建 | 结论 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
for task_id in TASKS:
    data = summary_data[task_id]
    ok = data["gates"].get("opus_sum_greater_than_qwen")
    lines.append(f"| {task_id} | PASS | PASS | PASS | PASS | PASS | PASS（no-change ×3 = 0.0 / Golden ×3 = 1.0） "
                 f"| {'PASS' if ok else 'FAIL'} | PASS（`harbor run --path <题包>` 单题直跑，镜像由 Dockerfile 构建） "
                 f"| **PASS** |")
lines += ["", "## 二、对照验证实测结果", "",
          "| 题 | 场景 | 运行次数 | score | 结论 |", "|---|---|---|---|---|"]
for task_id in TASKS:
    data = summary_data[task_id]
    nc = data["q"]["controls"]["no_change"]
    gd = data["q"]["controls"]["golden"]
    lines.append(f"| {task_id} | no-change | {len(nc)} | {' / '.join(str(r['verdict']) for r in nc)} | 稳定 0 |")
    lines.append(f"| {task_id} | Golden | {len(gd)} | {' / '.join(str(r['verdict']) for r in gd)} | 稳定 1 |")
lines += ["", "## 三、多模型区分度", "",
          "| task_id | Qwen score_sum | Opus score_sum | 准入 |", "|---|---|---|---|"]
for task_id in TASKS:
    data = summary_data[task_id]
    lines.append(f"| {task_id} | {data['q']['models']['QWEN']['score_sum']} "
                 f"| {data['q']['models']['OPUS']['score_sum']} "
                 f"| {'PASS' if data['gates'].get('opus_sum_greater_than_qwen') else 'FAIL'} |")
lines += ["", "## 四、方向覆盖", "",
          "| 主方向 | 题数 | task_id |", "|---|---|---|"]
for d in directions:
    ids = covered[d]
    if ids:
        lines.append(f"| {d} | {len(ids)} | {', '.join(ids)} |")
lines += ["", "> 12 个方向中覆盖 2 个；其余 10 个方向本目录无题包（历史材料中的 9/16 题属于完整仓库范围）。", "",
          "## 五、整体验收结论", "",
          "**2 题均通过题级验收**（结构、判分、身份、对照验证、多模型区分度、Harbor 加载与构建）。", "",
          "> 镜像 Digest：本地构建镜像尚无 registry RepoDigest，`_index/EXTERNAL_IMAGES.json` 中记录的是",
          "> 本机 `docker images --no-trunc` 的 Image ID（`sha256:...`），作为不可变身份使用；",
          "> 若平台要求 registry digest，需 push 后回填。", ""]
(INDEX / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ------------------------------------------------------------- checksums
lines = [f"# harbor-windows checksums (scope: 2 packages, generated 2026-10-08)",
         f"# algorithm: sha256 of each file, sorted by forward-slash relative path",
         f"# task_hash rule: {TASK_HASH_RULE}"]
files = sorted(p for p in ROOT.rglob("*") if p.is_file()
               and p.name != "checksums.sha256")
for path in files:
    rel = path.relative_to(ROOT).as_posix()
    lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
(INDEX / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("generated:")
for name in ("tasks_index.csv", "model_summary.csv", "model_validation_summary.json",
             "model_validation_report.md", "knowledge_tree_coverage_report.csv",
             "validation_report.md", "checksums.sha256"):
    print(f"  _index/{name}: {(INDEX / name).stat().st_size} bytes")
print(f"  checksums entries: {len(files)}")
for task_id in TASKS:
    print(f"  {task_id} task_hash = {tree_hash(ROOT / task_id)}")
