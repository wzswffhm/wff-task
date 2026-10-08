"""组装三个交付批次目录（对齐 zq 参考布局）。

批次目录最终形态：
    <批次>/
    ├── 交付文档.md
    ├── <TASKID>/                      五件套（instruction.md/task.toml/rubrics.json/environment/solution/tests）
    └── 跑分产物与轨迹/
        ├── README.md
        ├── summary.json
        └── <执行体>/{output/, reward.json, reward-details.json, 轨迹/}

本脚本只做机械组装，不写交付文档正文（正文人工维护）：
  1. 清理题包临时物（_rejudge / __pycache__ / .pyc）
  2. 复制五件套到 <批次>/<TASKID>/
  3. 回填判官重跑结果（reward.json / reward-details.json），旧值备份到 <执行体>/_prev/
  4. 重算 summary.json
  5. 生成 跑分产物与轨迹/README.md

用法:
    python assemble_batches.py --dry-run
    python assemble_batches.py
"""
import argparse
import json
import pathlib
import shutil

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"

TASKS = {
    "FIN3-WKN-149": "work-金融-资产管理-20261008",
    "FIN3-WKN-150": "work-金融-私募股权投资-20261008",
    "FIN3-WKN-151": "work-金融-商业银行-20261008",
}
MODELS = ["gpt-5.6-sol", "claude-opus-4-8", "qwen3.8-max-0902"]
EXECUTORS = ["oracle"] + MODELS
FILES = ["reward.json", "reward-details.json"]
SKIP_COPY = {"_rejudge", "__pycache__"}


def clean_task(task_dir, dry):
    """删除题包内不应交付的临时物。"""
    removed = []
    for p in list(task_dir.rglob("__pycache__")):
        removed.append(str(p.relative_to(task_dir)))
        if not dry:
            shutil.rmtree(p, ignore_errors=True)
    for p in list(task_dir.rglob("*.pyc")):
        removed.append(str(p.relative_to(task_dir)))
        if not dry:
            p.unlink(missing_ok=True)
    rj = task_dir / "_rejudge"
    if rj.exists():
        removed.append("_rejudge/")
        if not dry:
            shutil.rmtree(rj, ignore_errors=True)
    return removed


def copy_five(task_dir, dest, dry):
    if dest.exists():
        if not dry:
            shutil.rmtree(dest)
    if dry:
        return
    def ignore(_d, names):
        return [n for n in names if n in SKIP_COPY]
    shutil.copytree(task_dir, dest, ignore=ignore)


def sync_scores(task, batch_dir, dry):
    task_dir = H / task
    runs = batch_dir / "跑分产物与轨迹"
    out = {}
    for ex in EXECUTORS:
        src = task_dir / "_rejudge" / ex / "verifier"
        dst = runs / ex
        got = [f for f in FILES if (src / f).is_file()]
        if len(got) != 2:
            out[ex] = {"status": "missing", "files": got}
            continue
        rj = json.loads((src / "reward.json").read_text(encoding="utf-8"))
        if float(rj.get("criteria_counted") or 0) < 1:
            out[ex] = {"status": "unfinished"}
            continue
        if not dry:
            prev = dst / "_prev"
            prev.mkdir(parents=True, exist_ok=True)
            for f in FILES:
                if (dst / f).is_file():
                    shutil.copy2(dst / f, prev / f)
                shutil.copy2(src / f, dst / f)
        out[ex] = {
            "status": "ok",
            "reward": rj.get("reward"),
            "graded_score": rj.get("graded_score"),
            "criteria_counted": rj.get("criteria_counted"),
            "verifier_error": rj.get("verifier_error"),
        }
    return out


def write_summary(batch_dir, scores, task, dry):
    vals = [s["reward"] for m, s in scores.items()
            if m in MODELS and s.get("status") == "ok" and s.get("reward") is not None]
    mean = sum(vals) / len(vals) if vals else None
    payload = {
        "task": task,
        "batch": batch_dir.name,
        "scoring": "判官重跑（仅判官；复用已落盘交付物）——判据 description 变更后重算",
        "executors": scores,
        "model_mean": mean,
    }
    if not dry:
        (batch_dir / "跑分产物与轨迹" / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return mean


README_TMPL = """# 跑分产物与轨迹

- 批次：`{batch}`
- 题目：`{task}`
- 计分口径：本轮为**判官重跑**（仅重跑 Judge，复用已落盘的四执行体交付物）。
  原因：返修只改了判据 `description` 中的交付物路径（R01 等），
  `instruction.md` 与 `environment/input_files/` 未变，故按甲方口径仅需重跑判官。
- 判官：`claude-code`，`mode = individual`，模型 `qwen3.7-plus`，逐条判据独立会话。

## 目录

| 路径 | 内容 |
|---|---|
| `oracle/` | Oracle 预检（金标准基准） |
| `{models}` | 三模型跑分 |
| `<执行体>/output/` | 该执行体交付物（7 项） |
| `<执行体>/reward.json` | 主分（`finalize.py` 池化加权） |
| `<执行体>/reward-details.json` | 逐条判据明细 |
| `<执行体>/轨迹/` | 运行轨迹 |
| `<执行体>/_prev/` | 本轮回填前的旧分数备份（仅重跑过的执行体） |
| `summary.json` | 汇总与三模型均分 |

## 主分口径

`reward = Σ(正向 weight × value) / Σ(正向 weight)`，负向判据（`negate = true`）
按 `- weight × (1 - value)` 只计入分子。`verifier_error = 1` 表示评分不可信，
须重评而非记零分。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dry = a.dry_run

    for task, batch in TASKS.items():
        batch_dir = H / batch
        task_dir = H / task
        print("=" * 84)
        print(f"{task}  ->  {batch_dir.name}   dry={dry}")

        # 顺序要紧：判官结果来源在 <task>/_rejudge/，
        # 必须「先回填 → 再清理 _rejudge → 最后复制五件套」，否则回填拿不到源文件。
        scores = sync_scores(task, batch_dir, dry)

        removed = clean_task(task_dir, dry)
        print(f"  清理临时物: {removed if removed else '（无）'}")

        copy_five(task_dir, batch_dir / task, dry)
        print(f"  五件套 -> {batch_dir.name}/{task}/")
        for ex, s in scores.items():
            if s.get("status") == "ok":
                print(f"  回填 {ex:20s} reward={s['reward']} counted={s['criteria_counted']}")
            else:
                print(f"  !!   {ex:20s} {s}")

        mean = write_summary(batch_dir, scores, task, dry)
        print(f"  三模型均分 = {mean}")

        if not dry:
            (batch_dir / "跑分产物与轨迹" / "README.md").write_text(
                README_TMPL.format(batch=batch_dir.name, task=task,
                                   models=" / ".join(f"`{m}/`" for m in MODELS)),
                encoding="utf-8")
            print("  已写 跑分产物与轨迹/README.md")


if __name__ == "__main__":
    main()
