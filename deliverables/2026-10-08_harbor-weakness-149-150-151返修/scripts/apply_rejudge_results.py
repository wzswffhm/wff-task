"""判官重跑结果回填：把 _rejudge/<执行体>/verifier/ 的产物回填到批次跑分目录，并重算均分。

用法:
    python apply_rejudge_results.py --dry-run
    python apply_rejudge_results.py
"""
import argparse
import json
import pathlib
import shutil

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_ROOT = REPO / "harbor-weakness"
TASKS = {
    "FIN3-WKN-149": "work-金融-资产管理-20261008",
    "FIN3-WKN-150": "work-金融-私募股权投资-20261008",
    "FIN3-WKN-151": "work-金融-商业银行-20261008",
}
MODELS = ["gpt-5.6-sol", "claude-opus-4-8", "qwen3.8-max-0902"]
EXECUTORS = ["oracle"] + MODELS
FILES = ["reward.json", "reward-details.json"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for task, batch in TASKS.items():
        task_dir = TASK_ROOT / task
        runs = TASK_ROOT / batch / "跑分产物与轨迹"
        print(f"### {task}  ->  {batch}")
        summary = {}

        for ex in EXECUTORS:
            src_dir = task_dir / "_rejudge" / ex / "verifier"
            dst_dir = runs / ex
            got = [f for f in FILES if (src_dir / f).is_file()]
            if len(got) != 2:
                print(f"  !! {ex}: 重跑产物缺失（{src_dir} 只有 {got}）")
                continue
            reward = json.loads((src_dir / "reward.json").read_text(encoding="utf-8"))
            details = json.loads((src_dir / "reward-details.json").read_text(encoding="utf-8"))
            if a.dry_run:
                print(f"  DRY {ex}: reward={reward.get('reward')} "
                      f"counted={reward.get('criteria_counted')} verr={reward.get('verifier_error')}")
                continue

            prev = dst_dir / "_prev"
            prev.mkdir(parents=True, exist_ok=True)
            for f in FILES:
                if (dst_dir / f).is_file():
                    shutil.copy2(dst_dir / f, prev / f)
                shutil.copy2(src_dir / f, dst_dir / f)

            summary[ex] = {
                "reward": reward.get("reward"),
                "criteria_counted": reward.get("criteria_counted"),
                "verifier_error": reward.get("verifier_error"),
                "graded_score": details.get("score"),
            }
            print(f"  OK  {ex}: reward={reward.get('reward')} "
                  f"counted={reward.get('criteria_counted')} verr={reward.get('verifier_error')}")

        if a.dry_run or not summary:
            continue

        vals = [summary[m]["reward"] for m in MODELS if m in summary and summary[m]["reward"] is not None]
        mean = sum(vals) / len(vals) if vals else None
        summary["model_mean"] = mean
        summary["note"] = "判官重跑（仅判官，复用已落盘交付物）；判据 description 变更后重算。"
        (runs / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  三模型均分 = {mean}")
        print(f"  summary.json 已更新（备份旧值于各执行体 _prev/）")


if __name__ == "__main__":
    main()
