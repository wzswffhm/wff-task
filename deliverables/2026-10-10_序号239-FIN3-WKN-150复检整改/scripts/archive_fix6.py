# -*- coding: utf-8 -*-
"""FIN3-WKN-150 fix6 判分归档同步（序号 239 / 2026-10-09 复检整改）。

把 `_rejudge/<ex>/verifier/` 下的判分结果按 06 号文档口径覆盖到
`跑分产物与轨迹/<ex>/`，并重建 `summary.json`：

  • reward.json        <- verifier/reward.json（4 字段，2 空格缩进，与原归档同格式）
  • reward-details.json<- verifier/graded/reward.json（rewardkit 明细）或同名文件
  • summary.json       <- runs[].reward/verifier_error/criteria_counted；mean；round；各门禁

上一轮（fix5 / 1.0.5）的四条分数会压入 invalid_runs 留痕。

用法:
    python archive_fix6.py --check      # 只读，打印将要写入的内容
    python archive_fix6.py --apply      # 实际写入
"""
import argparse
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "FIN3-WKN-150"
TD = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix6-150" / TASK
ARC = TD / "跑分产物与轨迹"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5 = ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

PREV = {  # fix5（1.0.5）轮分数，作废留痕
    "oracle": 0.996591,
    "qwen3.8-max-0902": 0.7875,
    "claude-opus-4-8": 0.476136,
    "gpt-5.6-sol": 0.640909,
}
PREV_ROUND = "qc2/fix5-rejudged(2026-10-09 archived)"
NEW_ROUND = "fix6(qc3-remediation)+rejudge"

APPLY = "--apply" in sys.argv
CHECK = "--check" in sys.argv


def write_lf(path, text):
    """始终以 LF 写入（Windows 上 Path.write_text 会把 \\n 转成 CRLF）。"""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read_reward(ex):
    p = TD / "_rejudge" / ex / "verifier" / "reward.json"
    if not p.is_file():
        return None, f"缺少 {p}"
    d = json.loads(p.read_text(encoding="utf-8"))
    rem = p.parent / "reward_exit_message.json"
    if rem.is_file():
        return None, f"{ex} 未完成：{rem.read_text(encoding='utf-8')[:90]}"
    if float(d.get("criteria_counted") or 0) < 1:
        return None, f"{ex} criteria_counted=0"
    return d, ""


def find_details(ex):
    base = TD / "_rejudge" / ex / "verifier"
    for cand in (base / "graded" / "reward.json", base / "reward-details.json",
                 base / "graded" / "reward-details.json"):
        if cand.is_file() and cand.stat().st_size > 1000:
            return cand
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    results, errs = {}, []
    for ex in EXECUTORS:
        d, err = read_reward(ex)
        if d:
            results[ex] = d
        else:
            errs.append(err)

    print("=== 本轮判分结果 ===")
    for ex in EXECUTORS:
        d = results.get(ex)
        if d:
            print(f"  {ex:20} reward={d.get('reward')}  graded={d.get('graded_score')}  "
                  f"counted={d.get('criteria_counted')}  err={d.get('verifier_error')}")
        else:
            print(f"  {ex:20} ✘ {[e for e in errs if e.startswith(ex)]}")
    if errs and not (args.apply or args.check):
        print("\n存在未完成场次，中止。")
        return 1
    if errs:
        print("\n⚠ 存在未完成场次，不会写入 summary.json")
        if not args.apply:
            return 1

    g5 = [float(results[e]["reward"]) for e in G5 if e in results]
    mean = round(sum(g5) / len(g5), 6) if len(g5) == 3 else None
    print(f"\n  G5 均分 = {mean}  (G4 oracle = {results.get('oracle', {}).get('reward')})")
    if mean is not None:
        print(f"  门禁: oracle>0.85 -> {float(results['oracle']['reward']) > 0.85}; "
              f"mean<0.70 -> {mean < 0.70}; 非零 -> {all(v > 0 for v in g5)}")

    sc = json.loads((ARC / "summary.json").read_text(encoding="utf-8"))
    for r in sc["runs"]:
        d = results.get(r["model"])
        if d:
            r["reward"] = float(d["reward"])
            r["verifier_error"] = float(d.get("verifier_error") or 0)
            r["criteria_counted"] = float(d.get("criteria_counted") or 36)
            r["scored"] = True
    sc["task_version"] = "1.0.6"
    sc["round"] = NEW_ROUND
    sc["mean"] = mean
    sc["mean_gate"] = "<0.70"
    sc["any_model_scored"] = all(float(results[e]["reward"]) > 0 for e in G5)
    sc["declared_difficulty"] = "A1"
    sc["gate_pass"] = bool(float(results["oracle"]["reward"]) > 0.85 and mean < 0.70
                           and sc["any_model_scored"])

    new_invalid = [{
        "round": PREV_ROUND,
        "executor": ex,
        "reward": PREV[ex],
        "criteria_counted": 36.0,
        "verifier_error": 0.0,
        "reason": "金标利润桥补记非经常性损益行、包内 .sh 权限修正后作废；"
                  "按复检报告（2026-10-09，序号 239）第 4 条重跑四执行体",
    } for ex in EXECUTORS]
    sc["invalid_runs"] = new_invalid + sc.get("invalid_runs", [])

    print(f"\n=== 将写入 summary.json ===")
    print(f"  task_version={sc['task_version']}  round={sc['round']}  mean={sc['mean']}  "
          f"gate_pass={sc['gate_pass']}")
    print(f"  invalid_runs: {len(sc['invalid_runs'])} 条（新增 {len(new_invalid)} 条留痕）")
    for ex in EXECUTORS:
        p = find_details(ex)
        print(f"  {ex:20} details <- {p.name if p else '⚠ 未找到'}")

    if args.check and not args.apply:
        print("\n（--check：未写入）")
        return 0
    if not args.apply:
        print("\n（未加 --apply，未写入）")
        return 0

    for ex in EXECUTORS:
        d = results[ex]
        out = {"reward": float(d["reward"]), "graded_score": float(d.get("graded_score") or d["reward"]),
               "criteria_counted": float(d.get("criteria_counted") or 36),
               "verifier_error": float(d.get("verifier_error") or 0)}
        src = find_details(ex)
        if src:
            shutil.copy2(src, ARC / ex / "reward-details.json")
        write_lf(ARC / ex / "reward.json",
                 json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        print(f"  ✔ {ex} 已归档 reward.json{' + reward-details.json' if src else ''}")
    write_lf(ARC / "summary.json",
             json.dumps(sc, indent=2, ensure_ascii=False) + "\n")
    print("  ✔ summary.json 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
