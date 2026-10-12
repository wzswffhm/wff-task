# -*- coding: utf-8 -*-
"""核验序号 239 第五轮返修的本地题包、判分与飞书附件。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_DIR = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix7-150" / "FIN3-WKN-150"
BATCH_ZIP = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix7-150.zip"
TASK_ZIP = REPO / "harbor-weakness" / "FIN3-WKN-150_task.zip"
ANSWER_ZIP = REPO / "harbor-weakness" / "FIN3-WKN-150_answer.zip"
REPORT = REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第五轮返修" / "evidence" / "飞书最新质检报告.md"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5 = EXECUTORS[1:]
results: list[tuple[bool, str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    results.append((bool(condition), label, detail))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    memo_paths = [
        TASK_DIR / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        TASK_DIR / "tests" / "__golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        TASK_DIR / "跑分产物与轨迹" / "oracle" / "output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
    ]
    script_paths = [
        TASK_DIR / "solution" / "golden_output" / "FIN3-WKN-150_reproduce.py",
        TASK_DIR / "tests" / "__golden_output" / "FIN3-WKN-150_reproduce.py",
    ]
    check("三份金标备忘录一致", len({sha(path) for path in memo_paths}) == 1,
          ",".join(sha(path)[:12] for path in memo_paths))
    memo = memo_paths[0].read_text(encoding="utf-8")
    check("金标改为信息不足结论", "退出回报测算与信息边界" in memo
          and "可靠的绝对退出价值、MOIC/IRR 及固定年化回报" in memo
          and "待核实" in memo, "退出回报段")
    check("条件分析仍覆盖 R27 数值锚点", "290,160" in memo and "18,873" in memo
          and "1.26" in memo and "8.0%" in memo, "PE 16.12 / 18,000 情景")
    check("2029 不再被写成既定退出事实", "以标的公司 2029 年上市为主要退出路径" not in memo,
          "退出安排段")
    check("两份复算脚本一致", len({sha(path) for path in script_paths}) == 1,
          ",".join(sha(path)[:12] for path in script_paths))
    script = script_paths[0].read_text(encoding="utf-8")
    check("脚本输出同步修订", "退出回报测算与信息边界" in script
          and "参数以外的假设不得自行引入" in script and "待核实" in script, "reproduce.py")

    rubric_toml = (TASK_DIR / "tests" / "rubrics.toml").read_text(encoding="utf-8")
    rubric_json = json.loads((TASK_DIR / "rubrics.json").read_text(encoding="utf-8"))
    check("R27 运行态修订", "退出回报口径披露正确" in rubric_toml
          and "如按 2029 年上市" not in rubric_toml, "tests/rubrics.toml")
    item = next((item for item in rubric_json["items"] if item["id"] == "R27"), None)
    check("R27 设计态同步", item is not None and item["description"].startswith("退出回报口径披露正确"),
          item["description"][:30] if item else "missing")
    check("判据 36 条且双文件一致",
          len(rubric_json["items"]) == 36 and sum(1 for line in rubric_toml.splitlines()
                                                  if line.startswith("id = ")) == 36, "36/36")
    task_toml = (TASK_DIR / "task.toml").read_text(encoding="utf-8")
    check("版本 1.0.7", 'version = "1.0.7"' in task_toml, "task.toml")

    report = REPORT.read_text(encoding="utf-8")
    check("最新返修要求已归档", "参数以外的假设不得自行引入" in report and "R27" in report
          and "重跑受影响判官" in report, "飞书最新质检报告.md")

    summary = json.loads((TASK_DIR / "跑分产物与轨迹" / "summary.json").read_text(encoding="utf-8"))
    check("summary 1.0.7", summary.get("task_version") == "1.0.7", summary.get("round", ""))
    scores = {run["model"]: float(run["reward"]) for run in summary["runs"]}
    mean = round(sum(scores[model] for model in G5) / 3, 6)
    check("G4 oracle > 0.85", scores["oracle"] > 0.85, str(scores["oracle"]))
    check("G5 均分 < 0.70", mean < 0.70, str(mean))
    check("三模型非零", all(scores[model] > 0 for model in G5),
          ",".join(f"{model}={scores[model]}" for model in G5))
    check("summary 门禁", summary.get("gate_pass") is True and summary.get("declared_difficulty") == "A1",
          f"mean={summary.get('mean')}")

    for executor in EXECUTORS:
        reward = json.loads((TASK_DIR / "跑分产物与轨迹" / executor / "reward.json").read_text(encoding="utf-8"))
        details = json.loads((TASK_DIR / "跑分产物与轨迹" / executor / "reward-details.json").read_text(encoding="utf-8"))
        criteria = {criterion["id"]: criterion for criterion in details["reward"]["criteria"]}
        r27 = criteria.get("R27", {})
        check(f"{executor} reward/counted/err",
              float(reward["criteria_counted"]) == 36 and float(reward["verifier_error"]) == 0,
              f"reward={reward['reward']}")
        check(f"{executor} R27 有明确判定", "value" in r27,
              f"value={r27.get('value')}")

    check("批次包存在", BATCH_ZIP.is_file(), f"{BATCH_ZIP.stat().st_size:,} B" if BATCH_ZIP.exists() else "missing")
    if BATCH_ZIP.exists():
        with zipfile.ZipFile(BATCH_ZIP) as archive:
            names = archive.namelist()
            infos = {info.filename: info for info in archive.infolist()}
            crlf = [name for name in names if name.endswith((".sh", ".py", ".toml", ".md"))
                    and b"\r\n" in archive.read(name)]
            memo_in_zip = archive.read(f"{BATCH_ZIP.stem}/FIN3-WKN-150/solution/golden_output/"
                                       "FIN3-WKN-150_PreIPO投资决策备忘录.md")
        root = BATCH_ZIP.stem
        check("批次包顶层唯一", len({name.split("/")[0] for name in names}) == 1, root)
        check("批次包第二层唯一题目目录",
              {name.split("/")[1] for name in names if name.count("/") >= 1 and name.split("/")[1]} == {"FIN3-WKN-150"})
        check("批次包无禁入项", not any("_rejudge" in name or "__pycache__" in name
                                       or name.endswith((".pyc", ".out", ".err")) for name in names))
        modes = {name: (infos[name].external_attr >> 16) & 0o777 for name in names if name.endswith(".sh")}
        check("批次包 .sh 全 0755", modes and all(mode == 0o755 for mode in modes.values()),
              str({name.split('/')[-1]: oct(mode) for name, mode in modes.items()}))
        check("批次包 LF", not crlf, str(crlf))
        check("批次包四个 reward", sum(name.endswith("/reward.json") for name in names) == 4)
        check("批次包金标修订", b"\xe9\x80\x80\xe5\x87\xba\xe5\x9b\x9e\xe6\x8a\xa5\xe6\xb5\x8b\xe7\xae\x97\xe4\xb8\x8e\xe4\xbf\xa1\xe6\x81\xaf\xe8\xbe\xb9\xe7\x95\x8c" in memo_in_zip)

    for path in (TASK_ZIP, ANSWER_ZIP):
        check(path.name + " 存在", path.is_file(),
              f"{path.stat().st_size:,} B" if path.is_file() else "missing")
    if TASK_ZIP.exists():
        with zipfile.ZipFile(TASK_ZIP) as archive:
            info = {item.filename: (item.external_attr >> 16) & 0o777 for item in archive.infolist()}
            data = json.loads(archive.read("FIN3-WKN-150/rubrics.json"))
            check("task zip 权限与判据", info.get("FIN3-WKN-150/tests/test.sh") == 0o755
                  and len(data["items"]) == 36, "test.sh / items=36")
    if ANSWER_ZIP.exists():
        with zipfile.ZipFile(ANSWER_ZIP) as archive:
            info = {item.filename: (item.external_attr >> 16) & 0o777 for item in archive.infolist()}
            check("answer zip 权限", info.get("FIN3-WKN-150/solution/solve.sh") == 0o755, "solve.sh")

    print("检查项".ljust(56), "结果  说明")
    print("-" * 110)
    failed = 0
    for passed, label, detail in results:
        if not passed:
            failed += 1
        print(f"{'OK' if passed else 'FAIL'} {label.ljust(52)} {detail}")
    print("-" * 110)
    print(f"共 {len(results)} 项，未通过 {failed} 项")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
