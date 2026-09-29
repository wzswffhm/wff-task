#!/usr/bin/env python3
"""
validate_package.py — Windows 专项 Coding Bench 题包校验器

按《Windows 专项 Coding Bench 数据采购》(windwos-第二版) 的验收门禁，
对题包做结构与身份一致性校验，输出 PASS/FAIL/FLAG 报告。

用法：
    python validate_package.py --package <题包根目录>
    python validate_package.py --package <题包根目录> --json report.json
    python validate_package.py --harbor-assets <harbor-assets目录> --extras <delivery-extras目录>

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

# ---------------------------------------------------------------- 工具

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


# ---------------------------------------------------------------- 校验项

# 标准 Harbor 五件套（规范 5.1）
REQUIRED_TASK_FILES = ["task.toml", "instruction.md"]
REQUIRED_TASK_DIRS = ["environment", "solution", "tests"]

# 严禁出现在 Agent 可见环境中的内容
FORBIDDEN_IN_ENV = ["solution", "oracle", "golden", "answer", "reward"]
FORBIDDEN_IN_TESTS_VISIBLE = ["oracle.patch", "golden_output"]

# 已知的题面泄漏信号
LEAK_PATTERNS = [
    (re.compile(r"golden[_\s-]?patch", re.I), "提到 Golden Patch"),
    (re.compile(r"oracle[_\s-]?patch", re.I), "提到 Oracle Patch"),
    (re.compile(r"hidden[_\s-]?test", re.I), "提到隐藏测试"),
    (re.compile(r"FAIL_TO_PASS|PASS_TO_PASS", re.I), "提到 F2P/P2P 标识"),
    (re.compile(r"reward(\.json|\.txt)?\b", re.I), "提到 Reward 产物"),
]

INVALID_MARKER = re.compile(r"===SWELIVE_INVALID\s+([^=]+)===")


def check_structure(task_dir, r):
    """检查标准 Harbor 五件套结构。"""
    missing = []
    for f in REQUIRED_TASK_FILES:
        if not os.path.isfile(os.path.join(task_dir, f)):
            missing.append(f)
    for d in REQUIRED_TASK_DIRS:
        if not os.path.isdir(os.path.join(task_dir, d)):
            missing.append(d + "/")
    if missing:
        r.fail("结构", f"缺失标准 Harbor 必需项: {', '.join(missing)}",
               "规范 5.1 要求五件套: task.toml / instruction.md / environment/ / solution/ / tests/")
    else:
        r.ok("结构", "标准 Harbor 五件套齐全")


def check_task_toml(task_dir, r, expect_schema=None):
    """检查 task.toml 关键字段。"""
    p = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(p):
        return None
    txt = open(p, encoding="utf-8", errors="replace").read()

    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', txt, re.M)
    if not m:
        r.fail("task.toml", "缺少 version 字段")
    else:
        ver = m.group(1)
        r.ok("task.toml", f"version = {ver}")
        if expect_schema and ver != expect_schema:
            r.flag("task.toml", f"version '{ver}' 与期望 schema '{expect_schema}' 不一致",
                   "确认平台冻结的 Harbor Schema 版本；任何影响题面/环境/Solution/Tests 的修改须升级版本")

    # 关键段落
    for section in ["[metadata]", "[agent]", "[verifier]", "[environment]"]:
        if section in txt:
            r.ok("task.toml", f"含 {section}")
        else:
            r.fail("task.toml", f"缺少 {section}")

    # 资源与超时
    for field in ["timeout_sec", "docker_image", "cpus", "memory", "storage"]:
        if field in txt:
            r.ok("task.toml", f"含 {field}")
        else:
            r.flag("task.toml", f"缺少 {field}")

    # 12 小时上限（规范：单次端到端原则上 ≤12h）
    am = re.search(r"\[agent\][^\[]*?timeout_sec\s*=\s*([\d.]+)", txt, re.S)
    if am:
        secs = float(am.group(1))
        if secs > 43200:
            r.flag("task.toml", f"agent.timeout_sec = {secs:.0f}s ({secs/3600:.1f}h) 超过 12 小时上限",
                   "规范要求单次端到端评测原则上不超过 12 小时；需在 quality_review.md 说明理由")
        else:
            r.ok("task.toml", f"agent.timeout_sec = {secs/3600:.1f}h（≤12h）")
    return txt


def check_instruction_no_leak(task_dir, r):
    """检查 instruction.md 是否泄漏解法/答案。"""
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

    # 题面长度合理性（薄题检查）
    if len(txt.strip()) < 80:
        r.flag("题面质量", f"instruction.md 仅 {len(txt.strip())} 字符，可能是薄题")
    else:
        r.ok("题面质量", f"instruction.md {len(txt.strip())} 字符")


def check_env_no_solution(task_dir, r):
    """检查 environment/ 是否混入 Solution / 隐藏测试。"""
    env = os.path.join(task_dir, "environment")
    if not os.path.isdir(env):
        return
    bad = []
    for root, dirs, files in os.walk(env):
        for name in files + dirs:
            low = name.lower()
            for token in FORBIDDEN_IN_ENV:
                if token in low:
                    bad.append(os.path.relpath(os.path.join(root, name), task_dir))
                    break
    if bad:
        r.fail("环境泄漏", f"environment/ 内出现疑似 Solution/答案: {', '.join(bad[:10])}",
               "environment/ 禁止泄露 Solution 和隐藏 Tests")
    else:
        r.ok("环境泄漏", "environment/ 未见 Solution/答案/隐藏测试")


def check_tests(task_dir, r):
    """检查 tests/ 是否具备二值判分与 INVALID 区分能力。"""
    tests = os.path.join(task_dir, "tests")
    if not os.path.isdir(tests):
        return
    files = os.listdir(tests)
    r.ok("tests", f"tests/ 文件: {', '.join(sorted(files))}")

    # 识别验证入口
    entry = None
    for cand in ["test.ps1", "test.sh", "run_tests.sh", "test.py"]:
        if cand in files:
            entry = os.path.join(tests, cand)
            break
    if not entry:
        r.fail("tests", "未找到验证入口（test.ps1 / test.sh / test.py）")
        return

    txt = open(entry, encoding="utf-8", errors="replace").read()

    # INVALID 区分能力（规范 6.2 / 10.3）
    if INVALID_MARKER.search(txt) or "INVALID" in txt.upper():
        r.ok("INVALID 区分", "验证入口具备 INVALID 标记能力")
    else:
        r.fail("INVALID 区分", "验证入口未区分 INVALID（基础设施故障不得伪装成模型 0 分）",
               "规范 6.2: 存在 required 未执行/缺失/SKIP 或基础设施异常须标为 INVALID")

    # 二值判分
    has_binary = bool(re.search(r"(reward|score)\s*=\s*(1|1\.0|0|0\.0)\b", txt)) or \
                 "reward.txt" in txt or "reward.json" in txt
    if has_binary:
        r.ok("二值判分", "存在二值评分产物写出")
    else:
        r.flag("二值判分", "未在验证入口检测到 reward 产物写出；确认评分由 grade.py 等完成")

    # 旧评分语义残留（规范 9 第 6 项）
    for legacy in ["judge.toml", "rubric.json"]:
        if legacy in files:
            r.fail("旧评分残留", f"tests/ 仍含 {legacy}",
                   "规范第九章要求清除 judge.toml / rubric.json 的权重与部分分语义，改为 required F2P/P2P 二值判分")

    # grade.py 二值语义
    grade = os.path.join(tests, "grade.py")
    if os.path.isfile(grade):
        gt = open(grade, encoding="utf-8", errors="replace").read()
        if re.search(r"score\s*=\s*1\.0\s*if\s+resolved\s+else\s+0\.0", gt):
            r.ok("二值判分", "grade.py 实现 resolved → 1.0 / 0.0")
        if "FAIL_TO_PASS" in gt and "PASS_TO_PASS" in gt:
            r.ok("F2P/P2P", "grade.py 引用 FAIL_TO_PASS 与 PASS_TO_PASS")
        else:
            r.fail("F2P/P2P", "grade.py 未引用 F2P/P2P")
        # 权重/部分分残留
        if re.search(r"weight\s*[:=]", gt):
            weights = re.findall(r"weight\s*[:=]\s*([\d.]+)", gt)
            nonzero = [w for w in weights if float(w) not in (0.0, 1.0)]
            if nonzero:
                r.fail("权重残留", f"grade.py 存在非 0/1 权重: {nonzero}",
                       "规范禁止 testcase 权重与部分分")
            else:
                r.ok("权重检查", "grade.py 无部分分权重（仅 0/1）")


def check_no_change_and_golden_shape(task_dir, r):
    """检查是否存在 Golden / no-change 证据线索。"""
    tests = os.path.join(task_dir, "tests")
    if not os.path.isdir(tests):
        return
    files = " ".join(os.listdir(tests)).lower()
    spec = os.path.join(tests, "swelive_spec.json")
    if os.path.isfile(spec):
        try:
            d = json.load(open(spec, encoding="utf-8"))
            ve = d.get("verification_evidence", {})
            if ve:
                r.ok("运行证据声明", f"verification_evidence: {json.dumps(ve, ensure_ascii=False)}")
                if ve.get("required_base_runs") and ve.get("required_oracle_runs"):
                    r.ok("3+3 声明", f"声明 base/oracle 各 {ve.get('required_base_runs')}/{ve.get('required_oracle_runs')} 次")
            else:
                r.flag("运行证据声明", "swelive_spec.json 缺 verification_evidence")
            if d.get("FAIL_TO_PASS") and d.get("PASS_TO_PASS"):
                r.ok("F2P/P2P 声明", f"F2P={len(d['FAIL_TO_PASS'])} P2P={len(d['PASS_TO_PASS'])}")
            else:
                r.fail("F2P/P2P 声明", "spec 缺 FAIL_TO_PASS 或 PASS_TO_PASS")
        except Exception as e:
            r.fail("spec 解析", f"swelive_spec.json 解析失败: {e}")
    else:
        r.flag("spec", "未找到 swelive_spec.json（若用其他元数据文件请忽略）")


def check_extras(extras_dir, r):
    """检查 delivery-extras 伴随材料（规范 5.4 / 5.5）。"""
    if not extras_dir or not os.path.isdir(extras_dir):
        r.fail("伴随材料", "未提供 delivery-extras/ 目录",
               "规范 5.1: 缺少伴随材料的题目不得验收")
        return

    batch_files = ["batch_manifest.csv", "knowledge_tree_coverage_report.csv",
                   "validation_report.md", "model_summary.csv", "known_issues.md",
                   "checksums.sha256", "CHANGELOG.md"]
    missing_batch = [f for f in batch_files if not os.path.isfile(os.path.join(extras_dir, f))]
    if missing_batch:
        r.fail("伴随材料", f"批次级文件缺失: {', '.join(missing_batch)}")
    else:
        r.ok("伴随材料", "批次级 7 个汇总文件齐全")

    tasks_dir = os.path.join(extras_dir, "tasks")
    if not os.path.isdir(tasks_dir):
        r.fail("伴随材料", "缺 delivery-extras/tasks/ 目录")
        return

    task_ids = sorted(os.listdir(tasks_dir))
    if not task_ids:
        r.fail("伴随材料", "delivery-extras/tasks/ 为空")
        return
    r.ok("伴随材料", f"伴随材料覆盖 {len(task_ids)} 题")

    per_task = ["metadata", "evidence", "model_runs", "testcase_mapping.csv",
                "quality_review.md", "remediation_and_retest.md"]
    for tid in task_ids:
        base = os.path.join(tasks_dir, tid)
        miss = [x for x in per_task if not os.path.exists(os.path.join(base, x))]
        if miss:
            r.fail("伴随材料", f"{tid} 缺: {', '.join(miss)}")
        else:
            r.ok("伴随材料", f"{tid} 六项齐全")

        # model_runs 四模型
        mr = os.path.join(base, "model_runs")
        if os.path.isdir(mr):
            models = [d.lower() for d in os.listdir(mr)]
            for want in ["qwen", "opus"]:
                if not any(want in m for m in models):
                    r.fail("多模型", f"{tid} model_runs 缺 {want}")
            for want in ["glm", "kimi"]:
                if not any(want in m for m in models):
                    r.fail("多模型", f"{tid} model_runs 缺 {want}")

        # evidence 五项
        ev = os.path.join(base, "evidence")
        if os.path.isdir(ev):
            evs = [d.lower() for d in os.listdir(ev)]
            for want in ["no_change", "golden", "clean_room"]:
                if not any(want in e for e in evs):
                    r.flag("对照证据", f"{tid} evidence 缺 {want}")


def check_identity(harbor_dir, assets_dir, r):
    """检查 harbor JSON 与 assets 的身份一致性。"""
    if not harbor_dir or not os.path.isdir(harbor_dir):
        r.flag("身份", "未提供 harbor/ 平台 JSON 目录，跳过身份校验")
        return
    if not assets_dir or not os.path.isdir(assets_dir):
        r.flag("身份", "未提供 harbor-assets/ 目录，跳过身份校验")
        return

    jsons = [f for f in os.listdir(harbor_dir) if f.endswith(".json")]
    assets = [d for d in os.listdir(assets_dir) if os.path.isdir(os.path.join(assets_dir, d))]

    json_ids = {os.path.splitext(f)[0] for f in jsons}
    asset_ids = set(assets)

    only_json = json_ids - asset_ids
    only_asset = asset_ids - json_ids
    if only_json:
        r.fail("身份", f"仅在 harbor/ 出现的 task_id: {sorted(only_json)}")
    if only_asset:
        r.fail("身份", f"仅在 harbor-assets/ 出现的 task_id: {sorted(only_asset)}")
    if not only_json and not only_asset:
        r.ok("身份", f"{len(json_ids)} 题在 harbor/ 与 harbor-assets/ 中一一对应")

    # 检查每题的 instance_id 一致性
    for f in jsons:
        p = os.path.join(harbor_dir, f)
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            r.fail("身份", f"{f} 解析失败: {e}")
            continue
        iid = d.get("instance_id")
        expect = os.path.splitext(f)[0]
        if iid != expect:
            r.fail("身份", f"{f}: instance_id='{iid}' 与文件名 '{expect}' 不一致",
                   "规范 5.5: task_id 在文件名、task.toml、来源材料、平台配置中必须一致")
        # 检查 assets 侧 task.toml 的镜像与 JSON 的 docker_image 是否一致
        tt = os.path.join(assets_dir, expect, "task.toml")
        if os.path.isfile(tt):
            ttt = open(tt, encoding="utf-8", errors="replace").read()
            m = re.search(r'docker_image\s*=\s*"([^"]+)"', ttt)
            if m and d.get("docker_image") and m.group(1) != d["docker_image"]:
                r.fail("身份", f"{expect}: task.toml 与 harbor JSON 的 docker_image 不一致",
                       f"task.toml: {m.group(1)}\nharbor: {d['docker_image']}")
            elif m and d.get("docker_image"):
                r.ok("镜像一致", f"{expect} 镜像引用一致")

        # 缺 solution 提示
        if not os.path.isdir(os.path.join(assets_dir, expect, "solution")):
            r.fail("结构", f"{expect} 缺 solution/ 目录",
                   "规范 5.1 五件套要求提供 Oracle/Reference Solution")


def check_digest_recorded(pkg_root, r):
    """检查镜像不可变 Digest 是否另存。"""
    found = []
    for root, dirs, files in os.walk(pkg_root):
        for f in files:
            if "image" in f.lower() and f.endswith(".json"):
                found.append(os.path.join(root, f))
    if not found:
        r.flag("镜像身份", "未找到镜像清单文件（应另存不可变 Digest）")
        return
    for p in found:
        try:
            d = json.load(open(p, encoding="utf-8"))
            s = json.dumps(d)
            if "sha256:" in s or "digest" in s.lower():
                r.ok("镜像身份", f"{os.path.basename(p)} 含 digest 记录")
            else:
                r.flag("镜像身份", f"{os.path.basename(p)} 未见 digest 字段",
                       "规范 5.5: 镜像标签不是不可变身份，必须另存实际 Digest")
        except Exception as e:
            r.fail("镜像身份", f"{os.path.basename(p)} 解析失败: {e}")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="Windows 专项 Coding Bench 题包校验器")
    ap.add_argument("--package", help="题包根目录（自动探测 harbor/ harbor-assets/ delivery-extras/）")
    ap.add_argument("--harbor-assets", help="harbor-assets 目录（含每题子目录）")
    ap.add_argument("--harbor", help="harbor 目录（平台 JSON）")
    ap.add_argument("--extras", help="delivery-extras 目录")
    ap.add_argument("--schema-version", default="1.3", help="期望的 Harbor Schema 版本（默认 1.3）")
    ap.add_argument("--json", help="把结果写入 JSON 文件")
    args = ap.parse_args()

    r = Report()

    pkg = args.package
    assets = args.harbor_assets
    harbor = args.harbor
    extras = args.extras

    if pkg:
        if not os.path.isdir(pkg):
            print(f"错误: 目录不存在 {pkg}", file=sys.stderr)
            return 2
        # 自动探测（兼容 harbor/ 与 outside_harbor/ 两种命名）
        for name in ["harbor", "outside_harbor"]:
            cand = os.path.join(pkg, name)
            if os.path.isdir(cand) and not harbor:
                harbor = cand
        for name in ["harbor-assets", "outside_harbor-assets"]:
            cand = os.path.join(pkg, name)
            if os.path.isdir(cand) and not assets:
                assets = cand
        # 若直接指向某题目录
        if not assets and os.path.isfile(os.path.join(pkg, "task.toml")):
            assets = os.path.dirname(pkg)
            pkg = os.path.dirname(pkg)
        cand = os.path.join(pkg, "delivery-extras")
        if os.path.isdir(cand) and not extras:
            extras = cand

    if not assets and not pkg:
        print("错误: 需指定 --package 或 --harbor-assets", file=sys.stderr)
        return 2

    # 单题模式
    if assets and os.path.isfile(os.path.join(assets, "task.toml")):
        r.ok("模式", f"单题校验: {assets}")
        check_structure(assets, r)
        check_task_toml(assets, r, args.schema_version)
        check_instruction_no_leak(assets, r)
        check_env_no_solution(assets, r)
        check_tests(assets, r)
        check_no_change_and_golden_shape(assets, r)
    else:
        # 多题目录模式
        task_dirs = []
        if assets and os.path.isdir(assets):
            for d in sorted(os.listdir(assets)):
                full = os.path.join(assets, d)
                if os.path.isdir(full) and os.path.isfile(os.path.join(full, "task.toml")):
                    task_dirs.append((d, full))
        if not task_dirs:
            r.fail("模式", "未找到任何含 task.toml 的题目目录")
        else:
            r.ok("模式", f"批量校验 {len(task_dirs)} 题")
            for tid, full in task_dirs:
                check_structure(full, r)
                check_task_toml(full, r, args.schema_version)
                check_instruction_no_leak(full, r)
                check_env_no_solution(full, r)
                check_tests(full, r)
                check_no_change_and_golden_shape(full, r)

    # 身份与伴随材料
    check_identity(harbor, assets, r)
    check_extras(extras, r)
    if pkg:
        check_digest_recorded(pkg, r)

    print(r.render())

    if args.json:
        c = r.counts()
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": c, "items": r.items}, f, ensure_ascii=False, indent=2)
        print(f"\n报告已写入 {args.json}")

    return 1 if r.counts()["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
