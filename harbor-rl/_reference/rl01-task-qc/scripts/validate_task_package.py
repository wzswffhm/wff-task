#!/usr/bin/env python3
"""校验单个 RL0-1 Cowork 题包是否符合数据构造规范。

覆盖 task.toml 必备字段、字段取值、题包目录、功能型 skill 落地、
以及 tests/rubrics.json 的字段、权重与分布要求（≥2 条 +10、
内容质量正分占比 ≥30%）。

用法:
    python validate_task_package.py <task-dir> [--json]

退出码: 0 = 无 error；1 = 存在 error；2 = 用法或环境错误。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        print("需要 Python 3.11+（tomllib）或先安装 tomli", file=sys.stderr)
        raise SystemExit(2)

ALLOWED_WEIGHTS = (-10.0, -7.0, -3.0, 3.0, 7.0, 10.0)
ALLOWED_LEVEL_KEYS = {"0", "0.25", "0.5", "0.75", "1"}
REQUIRED_METADATA = (
    "task_id",
    "author_organization",
    "category",
    "domain",
    "domain_l2",
    "capabilities",
    "difficulty",
    "vl_dependency",
    "source_note",
    "tools",
    "task_complexity",
    "weakness_tag",
    "environment_template",
    "tool_set",
    "expected_tool_dependencies",
    "expected_skill_dependencies",
    "tags",
)
DIFFICULTIES = {"A1", "A2", "A3"}
COMPLEXITIES = {"C1", "C2", "C3", "C4", "C5"}
CRITERION_TYPES = {"objective", "subjective"}
CRITERION_NECESSITY = {"explicit", "implicit"}
CRITERION_KINDS = {"binary", "gradient"}
WEAKNESS_RE = re.compile(r"^W\d{2}")
CONTENT_QUALITY = "内容质量"
MIN_CRITICAL_ITEMS = 2
MIN_CONTENT_QUALITY_SHARE = 0.30


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def num_equal(value, target: float) -> bool:
    try:
        return abs(float(value) - target) < 1e-9
    except (TypeError, ValueError):
        return False


def check_toml(task_dir: Path, report: Report) -> dict | None:
    toml_path = task_dir / "task.toml"
    if not toml_path.is_file():
        report.error("缺少 task.toml")
        return None
    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report.error(f"task.toml 解析失败: {exc}")
        return None

    if data.get("schema_version") != "1.4":
        report.error(f'schema_version 必须为 "1.4"，当前为 {data.get("schema_version")!r}')

    artifacts = as_list(data.get("artifacts"))
    if not artifacts:
        report.error("artifacts 缺失或为空")
    else:
        for item in artifacts:
            if not isinstance(item, str) or not item.startswith("/"):
                report.error(f"artifacts 条目必须是以 / 开头的绝对路径: {item!r}")
    if "/logs/artifacts/output" not in artifacts:
        # 与 rewardkit 交付规范 §3.2 冲突：那边要求 artifacts 由交付物清单"机械展开、
        # 不增不减"，实测不加该项也能通过甲方质检。此处只作提示，不视为缺陷。
        report.warn('artifacts 未含 "/logs/artifacts/output"（rewardkit §3.2 口径下可接受）')
        for item in artifacts:
            if isinstance(item, str) and not item.startswith("/app/output/") and item != "/logs/artifacts/output":
                report.warn(f'artifacts 路径不符合 "/app/output/<交付物名>" 格式: {item!r}')

    task = data.get("task") or {}
    for key in ("name", "version", "description"):
        if not task.get(key):
            report.error(f"[task] 缺少 {key}")

    meta = data.get("metadata")
    if not isinstance(meta, dict):
        report.error("缺少 [metadata] 段")
        return data

    # skill_set / expected_*_dependencies 允许为空数组（无技能题、Skill Discovery 干扰项场景），
    # 因此只校验字段存在，非空校验交给下面的专门检查。
    for key in REQUIRED_METADATA:
        if key not in meta or meta.get(key) in (None, "", {}):
            report.error(f"[metadata] 缺少必填字段 {key}")
    if not as_list(meta.get("tags")):
        report.error("[metadata] tags 为空，需填写任务关键词")

    difficulty = meta.get("difficulty")
    if difficulty and difficulty not in DIFFICULTIES:
        report.error(f'difficulty 取值必须是 A1/A2/A3，当前为 {difficulty!r}')

    complexity = meta.get("task_complexity")
    if complexity and complexity not in COMPLEXITIES:
        report.error(f"task_complexity 取值必须是 C1–C5，当前为 {complexity!r}")

    if meta.get("vl_dependency") not in (None, "是", "否"):
        report.warn(f'vl_dependency 应为"是"或"否"，当前为 {meta.get("vl_dependency")!r}')

    weakness = as_list(meta.get("weakness_tag"))
    if not weakness:
        report.error("weakness_tag 至少需要 1 个")
    for tag in weakness:
        if not isinstance(tag, str) or not WEAKNESS_RE.match(tag):
            report.error(f'weakness_tag 需按算法词表填写（形如 "W07-流程跳步"）: {tag!r}')

    skill_set = as_list(meta.get("skill_set"))
    expected_skills = as_list(meta.get("expected_skill_dependencies"))
    orphan = [name for name in expected_skills if name not in skill_set]
    if orphan:
        report.error(f"expected_skill_dependencies 必须是 skill_set 的子集，越界项: {orphan}")
    category = str(meta.get("category") or "")
    if "discovery" in category.lower() and expected_skills and set(expected_skills) == set(skill_set):
        report.error("Skill Discovery 任务中 expected_skill_dependencies 必须严格小于 skill_set（需存在故意无关的 skill）")

    deliverables = as_list(meta.get("deliverables"))
    if not deliverables:
        report.error("[metadata.deliverables] 至少要有 1 条")
    for idx, item in enumerate(deliverables, start=1):
        if not isinstance(item, dict):
            report.error(f"deliverables #{idx} 不是表（应为 [[metadata.deliverables]]）")
            continue
        for key in ("path", "required", "desc"):
            if key not in item:
                report.error(f"deliverables #{idx} 缺少 {key}")
        path = item.get("path")
        if isinstance(path, str) and artifacts:
            if f"/app/output/{path}" not in artifacts and path not in artifacts:
                report.warn(f"deliverables #{idx} 的 path 未出现在 artifacts 中: {path!r}")

    env = data.get("environment") or {}
    if env.get("network_mode") == "no-network":
        report.error('claude-code 框架下 network_mode 不要写 "no-network"')
    if env.get("storage_mb") != 30720:
        report.warn(f"environment.storage_mb 规范值为 30720，当前为 {env.get('storage_mb')!r}")
    for key in ("os", "build_timeout_sec", "network_mode", "cpus", "memory_mb", "storage_mb"):
        if key not in env:
            report.warn(f"[environment] 缺少 {key}")

    env_env = env.get("env") or {}
    leaked = sorted(k for k in env_env if str(k).upper().startswith("JUDGE_"))
    if leaked:
        report.error(f"JUDGE_ 变量严禁写入 [environment.env]（当前泄漏: {leaked}）")

    verifier = data.get("verifier") or {}
    verifier_env = verifier.get("env") or {}
    for key in ("JUDGE_API_KEY", "JUDGE_BASE_URL"):
        if key not in verifier_env:
            report.warn(f"[verifier.env] 缺少必选项 {key}")
    for key, value in verifier_env.items():
        if not key.startswith("JUDGE_") and key in {"EVAL_API_KEY", "EVAL_API_BASE", "LITELLM_DROP_PARAMS"}:
            continue
        if not key.startswith("JUDGE_") and key.startswith("JUDGE"):
            report.warn(f"[verifier.env] 变量名不规范: {key}")
        if key.startswith("JUDGE_") and key not in ("JUDGE_API_KEY", "JUDGE_BASE_URL") \
                and isinstance(value, str) and "${" not in value:
            report.warn(f'[verifier.env] 可选项 {key} 建议写成 "${{{key}:-默认值}}"')

    return data


def check_layout(task_dir: Path, data: dict | None, report: Report) -> None:
    if not (task_dir / "instruction.md").is_file():
        report.error("缺少 instruction.md")
    else:
        text = (task_dir / "instruction.md").read_text(encoding="utf-8", errors="replace")
        if len(text.strip()) < 50:
            report.warn("instruction.md 内容过短，确认任务说明/产出要求/硬约束是否齐备")
    for name in ("environment", "tests", "solution"):
        if not (task_dir / name).is_dir():
            (report.error if name != "solution" else report.warn)(f"缺少 {name}/ 目录")
    # rewardkit 交付口径：原始评分细则放题目根目录 rubrics.json，
    # Harbor 侧计分文件是 tests/rubrics.toml。两处任一存在即可。
    if not (task_dir / "tests" / "rubrics.json").is_file() \
            and not (task_dir / "rubrics.json").is_file():
        report.error("缺少 rubrics.json（题目根目录或 tests/ 下）")

    meta = (data or {}).get("metadata") or {}
    for name in as_list(meta.get("skill_set")):
        skill_md = task_dir / "environment" / "skills" / str(name) / "SKILL.md"
        if not skill_md.is_file():
            report.error(f"skill_set 中的 {name!r} 未在 environment/skills/{name}/SKILL.md 落地")


def load_rubrics(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rubrics", "criteria", "items"):
            if isinstance(data.get(key), list):
                return data[key]
        if "description" in data:
            return [data]
    raise ValueError("rubrics.json 顶层应为数组，或含 rubrics/criteria/items 数组的对象")


def check_rubrics(task_dir: Path, report: Report) -> list | None:
    path = task_dir / "tests" / "rubrics.json"
    if not path.is_file():
        path = task_dir / "rubrics.json"      # rewardkit 交付口径
    if not path.is_file():
        return None
    try:
        items = load_rubrics(path)
    except Exception as exc:  # noqa: BLE001
        report.error(f"rubrics.json 解析失败: {exc}")
        return None
    if not items:
        report.error("rubrics.json 为空")
        return None

    seen_ids: set[str] = set()
    dimensions: set[str] = set()
    weights: list[float] = []
    critical = 0
    negative = 0
    positive_total = 0.0
    quality_positive_total = 0.0

    for idx, item in enumerate(items, start=1):
        label = f"rubrics #{idx}"
        if not isinstance(item, dict):
            report.error(f"{label} 不是对象")
            continue
        item_id = str(item.get("id") or "")
        if not item_id:
            report.error(f"{label} 缺少 id")
        elif item_id in seen_ids:
            report.error(f"{label} 的 id 重复: {item_id}")
        else:
            seen_ids.add(item_id)
            label = f"rubrics {item_id}"

        description = str(item.get("description") or "").strip()
        if len(description) < 8:
            report.error(f"{label} 缺少可判断的 description")
        for word in ("美观", "深入", "专业", "清晰"):
            if description.startswith(word) or f"{word}。" in description:
                report.warn(f'{label} 描述可能过于主观，需转成可观察锚点: "{description[:30]}…"')
                break

        dimension = str(item.get("dimension") or "").strip()
        if not dimension:
            report.error(f"{label} 缺少 dimension")
        else:
            dimensions.add(dimension)

        ctype = str(item.get("criterion_type") or "").strip()
        if ctype.lower() not in CRITERION_TYPES:
            report.error(f"{label} criterion_type 必须是 Objective/Subjective，当前为 {ctype!r}")
        elif ctype not in ("Objective", "Subjective"):
            report.warn(f"{label} criterion_type 大小写需与规范一致（当前 {ctype!r}）")

        necessity = str(item.get("criterion_necessity") or "").strip()
        if necessity.lower() not in CRITERION_NECESSITY:
            report.error(f"{label} criterion_necessity 必须是 Explicit/Implicit，当前为 {necessity!r}")
        elif necessity not in ("Explicit", "Implicit"):
            report.warn(f"{label} criterion_necessity 大小写需与规范一致（当前 {necessity!r}）")

        kind = str(item.get("type") or "").strip()
        if kind.lower() not in CRITERION_KINDS:
            report.error(f"{label} type 必须是 Binary/Gradient，当前为 {kind!r}")

        weight = item.get("weight")
        if not any(num_equal(weight, allowed) for allowed in ALLOWED_WEIGHTS):
            report.error(f"{label} weight 只能取 ±10/±7/±3，当前为 {weight!r}")
        else:
            value = float(weight)
            weights.append(value)
            if value == 10.0:
                critical += 1
            if value > 0:
                positive_total += value
                if dimension.startswith(CONTENT_QUALITY):
                    quality_positive_total += value
            else:
                negative += 1

        levels = item.get("levels")
        if kind.lower() == "gradient":
            if not isinstance(levels, dict) or not levels:
                report.error(f"{label} 为 gradient，必须给出 levels 档位")
            else:
                keys = {str(k) for k in levels}
                astray = sorted(keys - ALLOWED_LEVEL_KEYS)
                if astray:
                    report.error(f"{label} levels 档位键只能是 0/0.25/0.5/0.75/1，越界: {astray}")
                if len(keys) != 5:
                    report.warn(f"{label} levels 建议给满 5 档，当前 {len(keys)} 档")
                for key, text in levels.items():
                    if not str(text).strip():
                        report.error(f"{label} levels[{key}] 缺少判定描述")
        elif isinstance(levels, dict) and levels:
            report.warn(f"{label} 为 binary，不应带 levels")

    if critical < MIN_CRITICAL_ITEMS:
        report.error(f"每题至少要有 {MIN_CRITICAL_ITEMS} 条 +10 评分项，当前 {critical} 条")

    if positive_total:
        share = quality_positive_total / positive_total
        if share < MIN_CONTENT_QUALITY_SHARE:
            report.error(
                f"内容质量维度正分占比 {share:.0%}，低于要求的 {MIN_CONTENT_QUALITY_SHARE:.0%}"
            )
        else:
            report.note(f"内容质量维度正分占比 {share:.0%}")
    else:
        report.error("没有任何正分评分项")

    if len(weights) > 1 and len(set(weights)) == 1:
        report.warn("所有打分项权重相同，需按对任务结果的影响程度拉开区分度")
    if negative == 0:
        report.note("未设置负分项（非强制，确认是否需要覆盖误删/幻觉/合规等风险）")
    missing_dims = [d for d in ("指令遵循", CONTENT_QUALITY) if not any(x.startswith(d) for x in dimensions)]
    if missing_dims:
        report.error(f"缺少必须覆盖的维度: {missing_dims}")
    report.note(f"共 {len(items)} 条打分项，正分权重合计 {positive_total:g}，负分项 {negative} 条，+10 项 {critical} 条")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="校验单个 RL0-1 Cowork 题包")
    parser.add_argument("task_dir", help="题包目录（含 task.toml）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    task_dir = Path(args.task_dir).expanduser().resolve()
    if not task_dir.is_dir():
        print(f"目录不存在: {task_dir}", file=sys.stderr)
        return 2

    report = Report()
    data = check_toml(task_dir, report)
    check_layout(task_dir, data, report)
    check_rubrics(task_dir, report)

    ok = not report.errors
    if args.json:
        print(json.dumps(
            {
                "task_dir": str(task_dir),
                "ok": ok,
                "errors": report.errors,
                "warnings": report.warnings,
                "notes": report.notes,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if ok else 1

    print(f"[{'PASS' if ok else 'FAIL'}] {task_dir.name}  ({task_dir})")
    for label, group in (("ERROR", report.errors), ("WARN", report.warnings), ("INFO", report.notes)):
        for message in group:
            print(f"  {label}: {message}")
    if ok:
        print("  机械门禁通过；真实性、trigger 有效性、参考答案专业性仍需人工判断。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
