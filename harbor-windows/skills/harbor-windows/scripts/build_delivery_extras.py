#!/usr/bin/env python3
"""
build_delivery_extras.py — 生成 delivery-extras/ 伴随材料骨架

按《Windows 专项 Coding Bench 数据采购》(windwos-第二版) 5.4 / 5.5，
为一批题目生成**符合结构要求**的伴随材料骨架（含批次级 7 文件 + 题级 6 项）。

注意：本脚本只**生成骨架与占位**，不生成真实证据。
凡标记 TODO 的内容必须由出题人补齐，否则不得验收。

用法：
    # 对已存在的题包批量建骨架
    python build_delivery_extras.py \
        --assets outside_harbor-assets \
        --out delivery-extras

    # 单题
    python build_delivery_extras.py \
        --task-id Azure__azure-sdk-for-python-41822 \
        --assets outside_harbor-assets \
        --out delivery-extras

    # 只看会创建什么，不写盘
    python build_delivery_extras.py --assets outside_harbor-assets --out delivery-extras --dry-run

退出码：
    0  成功
    2  参数或读取错误
"""

import argparse
import datetime
import json
import os
import re
import sys

BATCH_FILES = {
    "batch_manifest.csv": (
        "task_id,task_version,task_hash,language,primary_direction,difficulty,"
        "f2p_count,p2p_count,status,notes\n"
        "TODO,TODO,TODO,TODO,TODO,TODO,0,0,PENDING,由 build_delivery_extras.py 生成骨架，需人工补齐\n"
    ),
    "knowledge_tree_coverage_report.csv": (
        "node_path,task_ids,count,notes\n"
        "TODO,TODO,0,TODO\n"
    ),
    "validation_report.md": (
        "# 批次验收报告\n\n"
        "> TODO：逐项填写。缺任一门的题目不得进入正式集。\n\n"
        "## 批次概况\n\n"
        "| 项 | 值 |\n|---|---|\n"
        "| 批次 ID | TODO |\n| 题目数量 | TODO |\n| 冻结日期 | TODO |\n"
        "| Harbor Schema | 1.3 |\n| Harness | harbor-rewardkit==0.1.7 |\n\n"
        "## 验收门禁\n\n"
        "| 门禁 | 结论 | 证据位置 |\n|---|---|---|\n"
        "| Windows 价值反事实 | TODO | delivery-extras/tasks/<id>/metadata/labels.json |\n"
        "| 标准 Harbor 五件套 | TODO | outside_harbor-assets/<id>/ |\n"
        "| 二值判分无权重 | TODO | outside_harbor-assets/<id>/tests/grade.py |\n"
        "| INVALID 与 0 分区分 | TODO | outside_harbor-assets/<id>/tests/test.ps1 |\n"
        "| Golden 3x1 | TODO | delivery-extras/tasks/<id>/evidence/golden/ |\n"
        "| no-change 3x0 | TODO | delivery-extras/tasks/<id>/evidence/no_change/ |\n"
        "| 干净重建复验 | TODO | delivery-extras/tasks/<id>/evidence/clean_room/ |\n"
        "| Qwen 3 + Opus 3 区分度 | TODO | delivery-extras/tasks/<id>/model_runs/ |\n"
        "| GLM/Kimi 可运行性 | TODO | delivery-extras/tasks/<id>/model_runs/ |\n"
        "| Hack/泄漏审查 | TODO | delivery-extras/tasks/<id>/quality_review.md |\n"
        "| 身份三元组一致 | TODO | delivery-extras/tasks/<id>/metadata/manifest.json |\n"
        "| 镜像 Digest 另存 | TODO | delivery-extras/EXTERNAL_IMAGES.json |\n"
        "| delivery-extras 齐全 | TODO | delivery-extras/ |\n\n"
        "## 一票否决项复查\n\n"
        "TODO：逐条对照 references/06-acceptance-gates.md 的 14 条。\n"
    ),
    "model_summary.csv": (
        "task_id,model,model_identity,runs_total,runs_valid,runs_invalid,"
        "model_score_sum,testcase_pass_sum,validity,notes\n"
        "TODO,Qwen3.8-Max-0902,TODO,3,0,0,0,0,PENDING,TODO\n"
        "TODO,Opus 5,TODO,3,0,0,0,0,PENDING,TODO\n"
        "TODO,GLM-5.3,TODO,1,0,0,0,0,PENDING,TODO\n"
        "TODO,Kimi K3,TODO,1,0,0,0,0,PENDING,TODO\n"
    ),
    "known_issues.md": (
        "# 已知问题\n\n"
        "| # | task_id | 问题 | 影响 | 状态 | 计划 |\n|---|---|---|---|---|---|\n"
        "| 1 | TODO | TODO | TODO | OPEN | TODO |\n\n"
        "> 注意：'证据完整性缺口' 也属于已知问题，必须在此登记。\n"
    ),
    "CHANGELOG.md": (
        "# 变更记录\n\n"
        "## [1.0.0] - TODO\n\n"
        "### 新增\n\n- 初始批次\n\n"
        "### 变更\n\n- TODO\n\n"
        "### 修复\n\n- TODO\n\n"
        "> 规则：任何影响 题面/环境/Solution/Tests/判分 的修改都必须升级 task_version 并重跑受影响验收。\n"
    ),
}

TASK_SUBDIRS = [
    "metadata",
    "evidence/no_change",
    "evidence/golden",
    "evidence/clean_room",
    "evidence/negative_and_equivalent_controls",
    "evidence/cleanup_and_restore",
    "model_runs/qwen3.8-max-0902",
    "model_runs/opus-5",
    "model_runs/glm-5.3",
    "model_runs/kimi-k3",
]

TODO_MD = "TODO：由出题人填写。\n"


def read_spec(assets, tid):
    spec_path = os.path.join(assets, tid, "tests", "swelive_spec.json")
    if not os.path.isfile(spec_path):
        return {}
    try:
        return json.load(open(spec_path, encoding="utf-8"))
    except Exception:
        return {}


def read_task_toml(assets, tid):
    p = os.path.join(assets, tid, "task.toml")
    if not os.path.isfile(p):
        return {}
    txt = open(p, encoding="utf-8", errors="replace").read()
    out = {}
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', txt, re.M)
    if m:
        out["version"] = m.group(1)
    m = re.search(r'docker_image\s*=\s*"([^"]+)"', txt)
    if m:
        out["docker_image"] = m.group(1)
    m = re.search(r'\[metadata\][^\[]*?tags\s*=\s*\[([^\]]*)\]', txt, re.S)
    if m:
        out["tags"] = [t.strip().strip('"') for t in m.group(1).split(",") if t.strip()]
    return out


def mkfile(path, content, dry):
    if dry:
        print(f"  [dry-run] 写文件 {path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        print(f"  [skip] 已存在，不覆盖: {path}")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"  [new] {path}")


def mksubdirs(root, subs, dry):
    for s in subs:
        p = os.path.join(root, s)
        if dry:
            print(f"  [dry-run] 建目录 {p}")
        else:
            os.makedirs(p, exist_ok=True)
    if not dry:
        print(f"  [dir] {root}/ 下 {len(subs)} 个子目录已就绪")


def build_task(assets, out, tid, dry):
    task_root = os.path.join(out, "tasks", tid)
    print(f"\n== {tid} ==")
    mksubdirs(task_root, TASK_SUBDIRS, dry)

    spec = read_spec(assets, tid)
    toml = read_task_toml(assets, tid)
    task_version = spec.get("task_version") or toml.get("version") or "1.0"

    # metadata 四件套
    src = {
        "_comment": "生成骨架：必须人工补齐 TODO 后才能通过验收",
        "task_id": tid,
        "task_version": task_version,
        "source": {"repo": "TODO", "base_commit": spec.get("base_commit", "TODO"),
                   "source_commit": spec.get("source_commit", "TODO"),
                   "pull_number": "TODO"},
        "license": {"spdx": "TODO", "allows_derivative": None,
                    "notes": "TODO：核对仓库 License"},
        "authorization": {"source": "TODO", "allows_evaluation_use": None,
                          "allows_vendor_delivery": None},
        "privacy": {"contains_personal_data": None, "contains_secrets": None,
                    "sanitized": None, "sanitization_notes": "TODO"},
        "windows_relevance": {"target_os": "Windows", "counterfactual_checked": None,
                              "would_hold_on_linux": None, "reason": "TODO"},
    }
    labels = {
        "_comment": "生成骨架：必须人工补齐 TODO 后才能通过验收",
        "task_id": tid, "task_version": task_version,
        "primary_direction": "TODO",
        "secondary_tags": ["TODO"],
        "language": "TODO", "task_type": "TODO",
        "windows_target": {"version": "TODO", "edition": "TODO",
                           "arch": "TODO", "locale": "TODO"},
        "windows_mechanism": {"core_mechanism": "TODO", "on_success_path": None,
                              "linux_equivalent_exists": None, "linux_equivalent_note": "TODO"},
        "difficulty": {"level": "TODO", "rationale": "TODO"},
        "knowledge_tree": {"node_path": ["TODO"], "coverage_note": "TODO"},
    }
    lineage = {
        "_comment": "生成骨架：必须人工补齐 TODO 后才能通过验收",
        "task_id": tid, "task_version": task_version,
        "lineage": {"derived_from": None, "derivation_type": "TODO", "parent_task_ids": [],
                    "notes": "TODO"},
        "contamination": {"checked": None, "risk_level": "TODO", "checked_against": ["TODO"],
                          "overlap_found": None, "mitigation": "TODO", "evidence": "TODO"},
        "duplication": {"checked": None, "is_duplicate": None, "is_surface_variant": None,
                        "similar_tasks": [], "notes": "TODO"},
        "hack_and_leak_review": {"reviewed": None,
                                 "network_seeking_answers": "TODO",
                                 "local_answer_search": "TODO",
                                 "verifier_tampering": "TODO",
                                 "stale_artifact_reuse": "TODO",
                                 "notes": "TODO：区分 尝试/成功访问/实际使用/已证明影响成绩 四层"},
    }
    manifest = {
        "_comment": "生成骨架：task_hash 与 artifacts 哈希需由 scripts/hash_package.py 或手动计算填入",
        "task_id": tid, "task_version": task_version, "task_hash": "TODO",
        "source_commit": spec.get("source_commit", "TODO"),
        "base_commit": spec.get("base_commit", "TODO"),
        "image_ref": toml.get("docker_image") or spec.get("image_ref", "TODO"),
        "image_digest": spec.get("image_digest", "TODO"),
        "artifacts": {"task_toml_sha256": "TODO", "instruction_md_sha256": "TODO",
                      "test_patch_sha256": "TODO", "oracle_patch_sha256": "TODO",
                      "spec_sha256": "TODO", "dockerfile_sha256": "TODO"},
        "windows_target": {"version": "TODO", "edition": "TODO", "arch": "TODO", "locale": "TODO"},
        "frozen_baseline": {
            "harbor_schema": "1.3", "harness": "harbor-rewardkit==0.1.7",
            "models": ["Qwen3.8-Max-0902", "Opus 5", "GLM-5.3", "Kimi K3"],
            "frozen_at": datetime.date.today().isoformat(),
            "tool_permissions": "TODO", "network_policy": "TODO",
            "sampling": {"temperature": 0.0, "top_p": 1.0},
            "budget": {"agent_timeout_sec": 43200, "verifier_timeout_sec": 7200},
        },
        "checksums": {"algorithm": "sha256", "file": "checksums.sha256",
                      "covers": ["outside_harbor/", "outside_harbor-assets/", "delivery-extras/"]},
        "reviewers": [{"role": "TODO", "name": "TODO", "reviewed_at": "TODO"}],
    }
    meta_dir = os.path.join(task_root, "metadata")
    for name, obj in [("source_and_license.json", src), ("labels.json", labels),
                      ("lineage_and_contamination.json", lineage), ("manifest.json", manifest)]:
        mkfile(os.path.join(meta_dir, name),
               json.dumps(obj, ensure_ascii=False, indent=2) + "\n", dry)

    # testcase_mapping.csv
    f2p = spec.get("FAIL_TO_PASS") or []
    p2p = spec.get("PASS_TO_PASS") or []
    rows = ["requirement_id,requirement_text,testcase_id,group,evidence"]
    for i, t in enumerate(f2p, 1):
        rows.append(f"R{i},TODO,{t},F2P,TODO")
    for i, t in enumerate(p2p, 1):
        rows.append(f"P{i},TODO,{t},P2P,TODO")
    if len(rows) == 1:
        rows.append("R1,TODO,TODO,F2P,TODO")
    mkfile(os.path.join(task_root, "testcase_mapping.csv"), "\n".join(rows) + "\n", dry)

    # quality_review.md / remediation_and_retest.md
    mkfile(os.path.join(task_root, "quality_review.md"),
           f"# 质检报告 — {tid}\n\n"
           f"## 质检结论\n\n`PENDING`\n\n"
           f"## 证据完整性\n\n| 项 | 状态 | 位置 |\n|---|---|---|\n"
           f"| Golden 3x1 | TODO | evidence/golden/ |\n"
           f"| no-change 3x0 | TODO | evidence/no_change/ |\n"
           f"| 干净重建复验 | TODO | evidence/clean_room/ |\n"
           f"| 反例与等价实现 | TODO | evidence/negative_and_equivalent_controls/ |\n"
           f"| 清理与恢复 | TODO | evidence/cleanup_and_restore/ |\n"
           f"| 模型运行 | TODO | model_runs/ |\n\n"
           f"## Hack / 泄漏审查（四层分级）\n\n"
           f"| 行为 | 尝试 | 成功访问 | 实际使用 | 已证明影响成绩 |\n|---|---|---|---|---|\n"
           f"| 联网搜答案/下载上游 Patch | TODO | TODO | TODO | TODO |\n"
           f"| 读本地 Solution/隐藏 Tests/Git 残留 | TODO | TODO | TODO | TODO |\n"
           f"| 改 Tests/Verifier/结果文件 | TODO | TODO | TODO | TODO |\n"
           f"| 复用旧二进制/伪造 PASS | TODO | TODO | TODO | TODO |\n\n"
           f"> 关键词未命中不能证明绝对无 Hack；请求失败也不能误写为下载成功。\n", dry)
    mkfile(os.path.join(task_root, "remediation_and_retest.md"),
           f"# 整改与复验 — {tid}\n\n"
           f"| # | 问题 | 根因 | 整改动作 | 复验方式 | 复验结论 |\n|---|---|---|---|---|---|\n"
           f"| 1 | TODO | TODO | TODO | TODO | TODO |\n\n" + TODO_MD, dry)

    # evidence 各目录占位说明
    for sub, title in [
        ("evidence/no_change", "no-change 对照（3 次均为 0）"),
        ("evidence/golden", "Golden 对照（3 次均为 1）"),
        ("evidence/clean_room", "干净重建 / 恢复后复验"),
        ("evidence/negative_and_equivalent_controls", "错误反例与等价实现对照"),
        ("evidence/cleanup_and_restore", "清理与恢复证据"),
    ]:
        mkfile(os.path.join(task_root, sub, "README.md"),
               f"# {title}\n\n"
               f"要求：\n"
               f"- 每次运行保留 原始日志 + report.json + reward 三件套\n"
               f"- 记录 run_id / image_digest / source_commit / log_sha256\n"
               f"- TODO：补齐实际运行证据\n\n"
               f"钩子：\n- status: TODO (VALID/INVALID/PENDING)\n- runs: TODO\n", dry)

    # model_runs 各模型占位
    for model in ["qwen3.8-max-0902", "opus-5", "glm-5.3", "kimi-k3"]:
        required = 3 if model in ("qwen3.8-max-0902", "opus-5") else 1
        mkfile(os.path.join(task_root, "model_runs", model, "README.md"),
               f"# 模型运行记录 — {model}\n\n"
               f"- 精确模型标识：TODO（必须写平台的准确版本串，如 Qwen3.8-Max-0902）\n"
               f"- 要求有效运行次数：**{required}**\n"
               f"- 采样参数：temperature / top_p / max_tokens = TODO\n\n"
               f"每次运行目录 `run-N/` 应含：\n"
               f"  - `trajectory.jsonl` / 轨迹\n"
               f"  - `patch.diff` 最终补丁\n"
               f"  - `per_testcase.json` 逐 testcase 结果（PASS/FAIL/SKIP/MISSING/ERROR/NOT_RUN）\n"
               f"  - `report.json` 评分报告\n"
               f"  - `meta.json`：run_id, image_digest, source_commit, log_sha256, 耗时, 有效性(VALID/INVALID)\n"
               f"  - `badcase_attribution.md`：若失败，归因到 题面/测试/环境/聚合器/证据/模型能力/Hack\n\n"
               f"> INVALID 运行必须查明原因并补跑，**不得计入难度统计**。\n", dry)
    return spec


def main():
    ap = argparse.ArgumentParser(description="生成 delivery-extras 伴随材料骨架")
    ap.add_argument("--assets", required=True, help="outside_harbor-assets 目录")
    ap.add_argument("--out", required=True, help="delivery-extras 输出目录")
    ap.add_argument("--task-id", action="append", default=None,
                    help="只处理指定 task_id（可重复）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写盘")
    args = ap.parse_args()

    if not os.path.isdir(args.assets):
        print(f"错误: assets 目录不存在 {args.assets}", file=sys.stderr)
        return 2

    if args.task_id:
        tids = args.task_id
        for t in tids:
            if not os.path.isdir(os.path.join(args.assets, t)):
                print(f"错误: 题目目录不存在 {os.path.join(args.assets, t)}", file=sys.stderr)
                return 2
    else:
        tids = sorted(d for d in os.listdir(args.assets)
                      if os.path.isdir(os.path.join(args.assets, d))
                      and os.path.isfile(os.path.join(args.assets, d, "task.toml")))
    if not tids:
        print("错误: 未找到任何含 task.toml 的题目", file=sys.stderr)
        return 2

    print(f"批次级骨架 → {args.out}")
    for name, content in BATCH_FILES.items():
        mkfile(os.path.join(args.out, name), content, args.dry_run)
    mkfile(os.path.join(args.out, "checksums.sha256"),
           "# 由 `sha256sum` 或 `scripts/hash_package.py` 生成；覆盖 outside_harbor/、"
           "outside_harbor-assets/、delivery-extras/\n# TODO\n", args.dry_run)
    mkfile(os.path.join(args.out, "EXTERNAL_IMAGES.json"),
           json.dumps({
               "_comment": "镜像不可变身份清单：标签不是身份，必须另存 Digest",
               "schema_version": 1,
               "images": [{"task": tid, "image": "TODO", "digest": "sha256:TODO",
                           "anonymous_manifest_status": None} for tid in tids],
           }, ensure_ascii=False, indent=2) + "\n", args.dry_run)

    for tid in tids:
        build_task(args.assets, args.out, tid, args.dry_run)

    print(f"\n完成：{len(tids)} 题骨架已{'模拟' if args.dry_run else '生成'}")
    print("提醒：所有 TODO / PENDING 必须补齐，否则按规范不得验收。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
