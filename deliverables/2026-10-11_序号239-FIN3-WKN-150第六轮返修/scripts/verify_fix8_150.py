# -*- coding: utf-8 -*-
"""核验序号 239 第六轮返修：本地题包、参考生成闭环、判分与飞书附件。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
SIX = REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
TASK_SRC = REPO / "harbor-weakness" / "FIN3-WKN-150"
TASK_DIR = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix8-150" / "FIN3-WKN-150"
BATCH_ROOT = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix8-150"
BATCH_ZIP = REPO / "harbor-weakness" / "work_fin-b01_20261006_fix8-150.zip"
TASK_ZIP = REPO / "harbor-weakness" / "FIN3-WKN-150_task.zip"
ANSWER_ZIP = REPO / "harbor-weakness" / "FIN3-WKN-150_answer.zip"
REPORT = SIX / "evidence" / "序号239_质检报告 (3).md"
GEN = SIX / "evidence" / "oracle_generation"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5 = EXECUTORS[1:]
SOLVE_TEMPLATE_SHA = "3f26ac81cb1c4583"
results: list[tuple[bool, str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    results.append((bool(condition), label, detail))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    arc = TASK_DIR / "跑分产物与轨迹"
    memo_paths = [
        TASK_DIR / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        TASK_DIR / "tests" / "__golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
        arc / "oracle" / "output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md",
    ]
    script_paths = [
        TASK_DIR / "solution" / "golden_output" / "FIN3-WKN-150_reproduce.py",
        TASK_DIR / "tests" / "__golden_output" / "FIN3-WKN-150_reproduce.py",
    ]

    # ---- 报告 5：f-string 修正 + 生成同源 ----
    script_src = script_paths[0].read_text(encoding="utf-8")
    bad_lines = []
    for number, line in enumerate(script_src.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith(("'", '"')):
            continue
        if re.search(r"\{[^{}]*\}", stripped) and not stripped.startswith(("f'", 'f"')):
            if "{" in stripped and "}" in stripped and ":." in stripped:
                bad_lines.append(number)
    check("复算脚本无缺 f 前缀的占位符行", not bad_lines, str(bad_lines))
    check("两份复算脚本一致", len({sha(p) for p in script_paths}) == 1,
          ",".join(sha(p)[:12] for p in script_paths))
    check("三份金标备忘录同源一致", len({sha(p) for p in memo_paths}) == 1,
          ",".join(sha(p)[:12] for p in memo_paths))
    memo = memo_paths[0].read_text(encoding="utf-8")
    check("生成备忘录无占位符残留",
          "{med_pe" not in memo and "{fm(" not in memo and "{stake_mid" not in memo
          and "{multiple" not in memo and "{irr" not in memo, "七个占位符 token")
    check("退出口径修订在位", "退出回报测算与信息边界" in memo and "待核实" in memo
          and "条件分析" in memo and "290,160" in memo and "1.26" in memo, "退出回报段")

    # ---- 报告 5/6：生成执行证据 ----
    gen_log = arc / "oracle" / "轨迹" / "generation.log"
    gen_json = arc / "oracle" / "轨迹" / "generation.json"
    gen_manifest = arc / "oracle" / "轨迹" / "generated_manifest.json"
    check("生成执行证据齐全", gen_log.is_file() and gen_json.is_file() and gen_manifest.is_file(),
          f"{gen_log.stat().st_size if gen_log.is_file() else '-'} B log")
    if gen_manifest.is_file():
        manifest = json.loads(gen_manifest.read_text(encoding="utf-8"))
        check("生成清单 7 项无缺失", not manifest.get("missing") and len(manifest.get("found", [])) == 7,
              f"{len(manifest.get('found', []))}/7")
        mismatch = [item["path"] for item in manifest.get("found", [])
                    if not (arc / "oracle" / "output" / item["path"]).is_file()
                    or sha(arc / "oracle" / "output" / item["path"]) != item["sha256"]]
        check("生成清单哈希与归档一致", not mismatch, str(mismatch))
    if gen_json.is_file():
        meta = json.loads(gen_json.read_text(encoding="utf-8"))
        check("生成容器返回码 0", meta.get("returncode") == 0,
              f"image={meta.get('image')} elapsed={meta.get('elapsed_seconds')}s")
    evidence_copy = GEN / "output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
    if evidence_copy.is_file():
        check("证据目录与归档产物一致", sha(evidence_copy) == sha(memo_paths[2]),
              sha(evidence_copy)[:12])

    # ---- 报告 7：[scoring] 等价配置 ----
    rubric_toml = (TASK_DIR / "tests" / "rubrics.toml").read_text(encoding="utf-8")
    import tomllib
    parsed = tomllib.loads(rubric_toml)
    check("[scoring] aggregation 已补", parsed.get("scoring", {}).get("aggregation") == "weighted_mean",
          str(parsed.get("scoring")))
    check("判据仍为 36 条且语义未变",
          len(parsed["criterion"]) == 36
          and sum(1 for c in parsed["criterion"] if c.get("negate")) == 2, "36 / neg 2")
    rubric_json = json.loads((TASK_DIR / "rubrics.json").read_text(encoding="utf-8"))
    check("R27 运行态/设计态一致", "退出回报口径披露正确" in rubric_toml
          and next(i for i in rubric_json["items"] if i["id"] == "R27")["description"].startswith("退出回报口径披露正确"),
          "R27")

    # ---- 平台模板未被改动 ----
    solve = (TASK_DIR / "solution" / "solve.sh").read_bytes()
    check("solve.sh 保持平台模板", hashlib.sha256(solve).hexdigest().startswith(SOLVE_TEMPLATE_SHA)
          and solve == (REPO / "harbor-weakness/FIN3-WKN-149/solution/solve.sh").read_bytes(),
          f"{len(solve)} B")
    check("镜像两份 golden 一致",
          {p.relative_to(TASK_DIR / "solution/golden_output").as_posix()
           for p in (TASK_DIR / "solution/golden_output").rglob("*") if p.is_file()}
          == {p.relative_to(TASK_DIR / "tests/__golden_output").as_posix()
              for p in (TASK_DIR / "tests/__golden_output").rglob("*") if p.is_file()}, "7 项")

    # ---- 报告 8：交付文档位置与文案 ----
    doc = BATCH_ROOT / "交付文档.md"
    check("交付文档位于批次根", doc.is_file(), f"{doc.stat().st_size:,} B" if doc.is_file() else "missing")
    if doc.is_file():
        text = doc.read_text(encoding="utf-8")
        check("交付文档版本与批次已校正",
              "1.0.8" in text and "work_fin-b01_20261006_fix8-150" in text
              and "0.650758" in text, "1.0.8 / fix8-150 / 0.650758")
        check("交付文档不再误记判据未变",
              "判据与上一轮**逐字一致**（本轮未改判据" not in text
              and "1.0.6 → 1.0.7 确有 `R27` 实体变更" in text,
              "R27 实改已登记")
        check("交付文档保留环境变量说明",
              "环境变量表" in text and "JUDGE_API_PROTOCOL" in text and "solve.sh" in text)
    check("题目目录内不再放交付文档", not (TASK_DIR / "交付文档.md").exists())

    task_toml = (TASK_DIR / "task.toml").read_text(encoding="utf-8")
    check("版本 1.0.8", 'version = "1.0.8"' in task_toml, "task.toml")

    # ---- 判分 ----
    summary = json.loads((arc / "summary.json").read_text(encoding="utf-8"))
    check("summary 1.0.8", summary.get("task_version") == "1.0.8", summary.get("round", ""))
    scores = {run["model"]: float(run["reward"]) for run in summary["runs"]}
    mean = round(sum(scores[m] for m in G5) / 3, 6)
    check("G4 oracle > 0.85", scores["oracle"] > 0.85, str(scores["oracle"]))
    check("G5 均分 < 0.70", mean < 0.70, str(mean))
    check("三模型非零", all(scores[m] > 0 for m in G5),
          ",".join(f"{m}={scores[m]}" for m in G5))
    check("summary 门禁", summary.get("gate_pass") is True
          and summary.get("declared_difficulty") == "A1", f"mean={summary.get('mean')}")

    for executor in EXECUTORS:
        reward = json.loads((arc / executor / "reward.json").read_text(encoding="utf-8"))
        details = json.loads((arc / executor / "reward-details.json").read_text(encoding="utf-8"))
        criteria = {c["id"]: c for c in details["reward"]["criteria"]}
        check(f"{executor} reward/counted/err",
              float(reward["criteria_counted"]) == 36 and float(reward["verifier_error"]) == 0,
              f"reward={reward['reward']}")
        check(f"{executor} R27 有明确判定", "value" in criteria.get("R27", {}),
              f"value={criteria.get('R27', {}).get('value')}")

    report = REPORT.read_text(encoding="utf-8")
    check("本轮质检报告已归档", "aggregation" in report and "f-string" in report
          and "批次根" in report, "序号239_质检报告 (3).md")

    # ---- 打包 ----
    check("批次包存在", BATCH_ZIP.is_file(),
          f"{BATCH_ZIP.stat().st_size:,} B" if BATCH_ZIP.exists() else "missing")
    if BATCH_ZIP.exists():
        with zipfile.ZipFile(BATCH_ZIP) as archive:
            names = archive.namelist()
            infos = {info.filename: info for info in archive.infolist()}
            crlf = [n for n in names if n.endswith((".sh", ".py", ".toml", ".md"))
                    and b"\r\n" in archive.read(n)]
            memo_in_zip = archive.read(f"{BATCH_ZIP.stem}/FIN3-WKN-150/solution/golden_output/"
                                       "FIN3-WKN-150_PreIPO投资决策备忘录.md")
        check("批次包顶层唯一", len({n.split("/")[0] for n in names}) == 1, BATCH_ZIP.stem)
        check("批次包交付文档在顶层", f"{BATCH_ZIP.stem}/交付文档.md" in names)
        check("批次包第二层唯一题目目录",
              {n.split("/")[1] for n in names if n.count("/") >= 2} == {"FIN3-WKN-150"})
        check("批次包无禁入项", not any("_rejudge" in n or "__pycache__" in n
                                       or n.endswith((".pyc", ".out", ".err")) for n in names))
        modes = {n: (infos[n].external_attr >> 16) & 0o777 for n in names if n.endswith(".sh")}
        check("批次包 .sh 全 0755", modes and all(m == 0o755 for m in modes.values()),
              str({n.split('/')[-1]: oct(m) for n, m in modes.items()}))
        check("批次包 LF", not crlf, str(crlf))
        check("批次包四个 reward", sum(n.endswith("/reward.json") for n in names) == 4)
        check("批次包含生成执行证据",
              any(n.endswith("oracle/轨迹/generation.log") for n in names)
              and any(n.endswith("oracle/轨迹/generated_manifest.json") for n in names))
        check("批次包金标无占位符",
              b"{med_pe" not in memo_in_zip and b"{fm(" not in memo_in_zip)

    for path in (TASK_ZIP, ANSWER_ZIP):
        check(path.name + " 存在", path.is_file(),
              f"{path.stat().st_size:,} B" if path.is_file() else "missing")
    if TASK_ZIP.exists():
        with zipfile.ZipFile(TASK_ZIP) as archive:
            info = {i.filename: (i.external_attr >> 16) & 0o777 for i in archive.infolist()}
            data = json.loads(archive.read("FIN3-WKN-150/rubrics.json"))
            check("task zip 权限与判据", info.get("FIN3-WKN-150/tests/test.sh") == 0o755
                  and len(data["items"]) == 36, "test.sh / items=36")
    if ANSWER_ZIP.exists():
        with zipfile.ZipFile(ANSWER_ZIP) as archive:
            info = {i.filename: (i.external_attr >> 16) & 0o777 for i in archive.infolist()}
            check("answer zip 权限", info.get("FIN3-WKN-150/solution/solve.sh") == 0o755, "solve.sh")

    print("检查项".ljust(52), "结果  说明")
    print("-" * 112)
    failed = 0
    for passed, label, detail in results:
        if not passed:
            failed += 1
        print(f"{'OK' if passed else 'FAIL'} {label.ljust(48)} {detail}")
    print("-" * 112)
    print(f"共 {len(results)} 项，未通过 {failed} 项")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
