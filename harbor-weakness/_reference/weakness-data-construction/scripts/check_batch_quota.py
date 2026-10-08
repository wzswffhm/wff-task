#!/usr/bin/env python3
"""检查 RL0-1 Cowork 一批数据的配额与分布。

输入可以是：题包目录（递归读取 task.toml）、CSV、JSON 或 JSONL。
CSV/JSON 每行需要能取到这些字段（缺的字段会被记为缺失而非报错退出）：
task_id, domain, domain_l2, domain_l3, category, difficulty, task_complexity,
weakness_tag（分号/竖线/逗号分隔）。

用法:
    python check_batch_quota.py <path> [--total 1000] [--min 50] [--max 250]
                                [--weakness-vocab vocab.json] [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:
        print("需要 Python 3.11+（tomllib）或先安装 tomli", file=sys.stderr)
        raise SystemExit(2)

COMPLEXITY_QUOTA = {"C1": 120, "C2": 250, "C3": 350, "C4": 180, "C5": 100}
DIFFICULTY_QUOTA = {"A1": 0.20, "A2": 0.60, "A3": 0.20}
SPECIALTY_QUOTA = {
    "skill-discovery": 200,
    "skill-generation": 200,
    "skill-editing": 200,
    "skill-dependency": 200,
    "dependency-aware-workflow": 200,
    "workflow-dependency": 200,
    "subagent-workflow": 200,
}
MAX_SAME_L3 = 2
SPLIT_CHARS = ";|,、\n"


def split_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value)
    for ch in SPLIT_CHARS[1:]:
        text = text.replace(ch, SPLIT_CHARS[0])
    return [part.strip() for part in text.split(SPLIT_CHARS[0]) if part.strip()]


def normalize_row(raw: dict) -> dict:
    return {
        "task_id": raw.get("task_id") or raw.get("id") or "",
        "domain": (raw.get("domain") or "").strip(),
        "domain_l2": (raw.get("domain_l2") or "").strip(),
        "domain_l3": (raw.get("domain_l3") or "").strip(),
        "category": (raw.get("category") or "").strip().lower(),
        "difficulty": (raw.get("difficulty") or "").strip(),
        "task_complexity": (raw.get("task_complexity") or "").strip(),
        "weakness_tag": split_tags(raw.get("weakness_tag")),
    }


def rows_from_task_dirs(root: Path) -> list[dict]:
    rows = []
    for toml_path in sorted(root.rglob("task.toml")):
        try:
            meta = (tomllib.loads(toml_path.read_text(encoding="utf-8")).get("metadata") or {})
        except Exception as exc:  # noqa: BLE001
            print(f"WARN: 解析失败 {toml_path}: {exc}", file=sys.stderr)
            continue
        rows.append(normalize_row(meta))
    return rows


def load_rows(path: Path) -> list[dict]:
    if path.is_dir():
        return rows_from_task_dirs(path)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".csv":
        return [normalize_row(row) for row in csv.DictReader(text.splitlines())]
    if suffix == ".jsonl":
        return [normalize_row(json.loads(line)) for line in text.splitlines() if line.strip()]
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ("rows", "items", "data", "tasks"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("JSON 顶层应为数组，或含 rows/items/data/tasks 数组的对象")
        return [normalize_row(row) for row in data]
    raise ValueError(f"不支持的输入类型: {path.suffix or path.name}")


def pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "0.0%"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查一批 RL0-1 Cowork 数据的配额与分布")
    parser.add_argument("path", help="题包目录 / CSV / JSON / JSONL")
    parser.add_argument("--total", type=int, default=1000, help="该批次的目标总条数（默认 1000）")
    parser.add_argument("--min", dest="min_count", type=int, default=50, help="每种 weakness 最低覆盖条数")
    parser.add_argument("--max", dest="max_count", type=int, default=250, help="每种 weakness 最高覆盖条数")
    parser.add_argument("--weakness-vocab", help="JSON 文件，内容为 weakness 编号/名称数组")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args()

    source = Path(args.path).expanduser().resolve()
    if not source.exists():
        print(f"路径不存在: {source}", file=sys.stderr)
        return 2
    try:
        rows = load_rows(source)
    except Exception as exc:  # noqa: BLE001
        print(f"读取失败: {exc}", file=sys.stderr)
        return 2
    if not rows:
        print("没有读到任何数据行", file=sys.stderr)
        return 2

    total = len(rows)
    full_batch = total >= args.total
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    if not full_batch:
        notes.append(f"当前 {total} 条，未达目标批次 {args.total} 条；绝对配额只做进度提示，不判失败")

    weakness_counter: Counter[str] = Counter()
    vocabulary = None
    if args.weakness_vocab:
        vocabulary = [str(x) for x in json.loads(Path(args.weakness_vocab).read_text(encoding="utf-8"))]
    for row in rows:
        for tag in row["weakness_tag"]:
            weakness_counter[tag] += 1
        if not row["weakness_tag"]:
            errors.append(f"{row['task_id'] or '<无 task_id>'} 缺少 weakness_tag（每条至少覆盖 1 个）")

    if vocabulary:
        expected_weakness = vocabulary
    else:
        expected_weakness = sorted(weakness_counter) or [f"W{i:02d}" for i in range(1, 15)]
        warnings.append(
            "未提供 --weakness-vocab，按数据中出现的标签（或 W01–W14 占位）统计；"
            "14 种 weakness 的官方词表需向算法侧取全后重跑"
        )
    if len(expected_weakness) != 14:
        warnings.append(f"参与统计的 weakness 词表有 {len(expected_weakness)} 项，规范要求覆盖 14 种")

    for tag in expected_weakness:
        count = weakness_counter.get(tag, 0)
        if count == 0:
            (errors if full_batch else warnings).append(f"weakness {tag} 覆盖 0 条，必须覆盖全部 14 种")
        elif count < args.min_count:
            (errors if full_batch else warnings).append(f"weakness {tag} 覆盖 {count} 条，低于下限 {args.min_count}")
        if count > args.max_count:
            errors.append(f"weakness {tag} 覆盖 {count} 条，超过上限 {args.max_count}")

    complexity_counter = Counter(row["task_complexity"] for row in rows if row["task_complexity"])
    for level, expected in COMPLEXITY_QUOTA.items():
        count = complexity_counter.get(level, 0)
        if not count:
            warnings.append(f"task_complexity {level} 没有数据")
            continue
        if full_batch:
            low, high = expected * 0.8, expected * 1.2
            if not low <= count <= high:
                warnings.append(f"task_complexity {level} 有 {count} 条，目标 {expected} 条（±20% 外）")

    difficulty_counter = Counter(row["difficulty"] for row in rows if row["difficulty"])
    for level, share in DIFFICULTY_QUOTA.items():
        count = difficulty_counter.get(level, 0)
        actual = count / total if total else 0
        if full_batch and abs(actual - share) > 0.05:
            errors.append(f"难度 {level} 占比 {actual:.1%}，偏离目标 {share:.0%} 超过 5 个百分点")

    domain_counter = Counter(row["domain"] for row in rows if row["domain"])
    if domain_counter:
        values = list(domain_counter.values())
        spread = (max(values) - min(values)) / (sum(values) / len(values))
        if spread > 0.5:
            warnings.append(
                f"领域分布不均：最多 {max(values)} 条、最少 {min(values)} 条（相对落差 {spread:.0%}），规范要求平均覆盖"
            )

    l3_counter = Counter(
        f"{row['domain']}/{row['domain_l3']}" for row in rows if row["domain_l3"]
    )
    for label, count in l3_counter.items():
        if count > MAX_SAME_L3:
            errors.append(f"三级标签 {label} 有 {count} 道题，规范要求同一三级标签不超过 {MAX_SAME_L3} 道")

    category_counter = Counter(row["category"] for row in rows if row["category"])
    for name, count in category_counter.items():
        quota = SPECIALTY_QUOTA.get(name)
        if quota and count > quota:
            errors.append(f"专项分类 {name} 有 {count} 条，超过配额 {quota} 条")
    unknown = sorted(set(category_counter) - set(SPECIALTY_QUOTA)) if category_counter else []
    if unknown:
        notes.append(f"未在配额表中的 category: {unknown}（确认是否属于专项数据命名）")

    payload = {
        "source": str(source),
        "total": total,
        "full_batch": full_batch,
        "weakness": dict(weakness_counter.most_common()),
        "complexity": dict(complexity_counter),
        "difficulty": dict(difficulty_counter),
        "domain": dict(domain_counter.most_common()),
        "category": dict(category_counter.most_common()),
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
        "ok": not errors,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not errors else 1

    print(f"[{'PASS' if not errors else 'FAIL'}] {source}  共 {total} 条")
    print("\nweakness 覆盖（下限 {}-上限 {}）".format(args.min_count, args.max_count))
    for tag in expected_weakness:
        count = weakness_counter.get(tag, 0)
        bar = "#" * min(int(count / max(args.max_count, 1) * 40), 40)
        print(f"  {tag:<18} {count:>5}  {bar}")
    print("\ntask_complexity（当前/目标）: " + "  ".join(
        f"{k}={complexity_counter.get(k, 0)}/{COMPLEXITY_QUOTA[k]}" for k in COMPLEXITY_QUOTA
    ))
    print("difficulty:      " + "  ".join(
        f"{k}={difficulty_counter.get(k, 0)}({pct(difficulty_counter.get(k, 0), max(total, 1))})"
        for k in DIFFICULTY_QUOTA
    ))
    print("domain:          " + "  ".join(f"{k}={v}" for k, v in domain_counter.most_common()))
    if category_counter:
        print("category:        " + "  ".join(f"{k}={v}" for k, v in category_counter.most_common()))
    for label, group in (("ERROR", errors), ("WARN", warnings), ("INFO", notes)):
        for message in group:
            print(f"  {label}: {message}")
    if not full_batch:
        print(f"\n提示：补足到 {args.total} 条后再跑一次，绝对配额才具备判定意义。")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
