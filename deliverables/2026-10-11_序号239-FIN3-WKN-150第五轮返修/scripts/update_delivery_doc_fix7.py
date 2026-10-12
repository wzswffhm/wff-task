# -*- coding: utf-8 -*-
"""按第五轮终态更新 FIN3-WKN-150 交付文档。"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
DOC = (REPO / "harbor-weakness" / "work_fin-b01_20261006_fix7-150" / "FIN3-WKN-150"
       / "交付文档.md")
SUMMARY = DOC.parent / "跑分产物与轨迹" / "summary.json"
APPLY = "--apply" in sys.argv


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1, got {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = DOC.read_text(encoding="utf-8")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    scores = {run["model"]: float(run["reward"]) for run in summary["runs"]}
    mean = summary["mean"]

    replacements = [
        ("work_fin-b01_20261006_fix6", "work_fin-b01_20261006_fix7", "batch names"),
        ("1.0.6", "1.0.7", "version tokens"),
        ("第四轮：复检整改后判分重跑", "第五轮：退出回报口径整改后判分重跑", "round name"),
        ("2026-10-10（第四轮", "2026-10-11（第五轮", "package date"),
        ("fix6 / 1.0.6", "fix7 / 1.0.7", "section 3.2.3 label"),
        ("fix6(qc3-remediation)+rejudge", "fix7(exit-assumption-remediation)+rejudge", "summary round"),
    ]
    for old, new, label in replacements:
        count = text.count(old)
        print(f"{label}: {count}")
        if count:
            text = text.replace(old, new)

    score_rows = [
        ("| `oracle`（G4） | 0.996591 | **1.000000** | +0.003409 |",
         f"| `oracle`（G4） | 1.000000 | **{scores['oracle']:.6f}** | {scores['oracle'] - 1.0:+.6f} |"),
        ("| `qwen3.8-max-0902` | 0.787500 | **0.765909** | −0.021591 |",
         f"| `qwen3.8-max-0902` | 0.765909 | **{scores['qwen3.8-max-0902']:.6f}** | "
         f"{scores['qwen3.8-max-0902'] - 0.765909:+.6f} |"),
        ("| `gpt-5.6-sol` | 0.640909 | **0.654545** | +0.013636 |",
         f"| `gpt-5.6-sol` | 0.654545 | **{scores['gpt-5.6-sol']:.6f}** | "
         f"{scores['gpt-5.6-sol'] - 0.654545:+.6f} |"),
        ("| `claude-opus-4-8` | 0.476136 | **0.573864** | +0.097728 |",
         f"| `claude-opus-4-8` | 0.573864 | **{scores['claude-opus-4-8']:.6f}** | "
         f"{scores['claude-opus-4-8'] - 0.573864:+.6f} |"),
        ("| **G5 均分** | 0.634848 | **0.664773** | +0.029925 |",
         f"| **G5 均分** | 0.664773 | **{mean:.6f}** | {mean - 0.664773:+.6f} |"),
    ]
    # The score table may appear in README-like summary or section 3.2.3; replace all exact rows.
    for old, new in score_rows:
        if old in text:
            text = text.replace(old, new)
        else:
            print(f"score row not found (skipped): {old[:50]}")

    # Section 10 title/version and latest round marker.
    text = replace_once(
        text,
        "## 10. 第四轮整改记录（2026-10-10，批次 `work_fin-b01_20261006_fix7-150`，`[task].version` 1.0.7）",
        "## 10. 第四轮整改记录（2026-10-10，批次 `work_fin-b01_20261006_fix7-150`，`[task].version` 1.0.7）",
        "section 10 title",
    ) if "## 10. 第四轮整改记录（2026-10-10，批次 `work_fin-b01_20261006_fix7-150`，`[task].version` 1.0.7）" in text else text

    # Update known fix6 round labels.
    text = text.replace("fix6(qc3-remediation)+rejudge", "fix7(exit-assumption-remediation)+rejudge")
    text = text.replace("fix6/1.0.6", "fix7/1.0.7")
    text = text.replace("第四轮 fix6", "第五轮 fix7")
    text = text.replace("第四轮：复检整改后判分重跑", "第五轮：退出回报口径整改后判分重跑")

    section_11 = f"""

## 11. 第五轮整改记录（2026-10-11，批次 `work_fin-b01_20261006_fix7-150`，`[task].version` 1.0.7）

> 依据飞书《序号239质检报告》（2026-10-10 快照 20261010_131629）。本轮核心问题：原参考答案与 `R27`
> 将“2029 年上市退出、2027 年承诺利润 18,000 万元 × PE 16.12、持有三年”作为固定事实基准，但 32 号材料
> 明确“参数以外的假设不得自行引入”，33 号材料仅规定 2029-12-31 前完成上市申报，并未规定退出时点与
> 退出利润口径；因此应接受信息不足结论，或仅将明确授权的情景作为条件分析。

| 报告条目 | 处置 | 闭环证据 |
|---|---|---|
| 2【待改】退出回报无依据固定基准 | 金标第七节改为“退出回报测算与信息边界”：先明确退出时点、退出日估值口径、锁定减持期和退出日持股比例缺失，可靠绝对退出价值、MOIC/IRR 与固定年化回报均标注“待核实”；再把 290,160 / 18,873 / 1.26 / 8.0% 明确为**条件分析**，并说明该情景不构成材料已确认事实。退出安排同步改为“33 号材料仅约束上市申报，不等于完成上市或退出” | 两份 golden 与复算脚本逐字同步；`check_package.py` #3 两份 golden 一致 |
| 2【待改】R27 只认固定退出情景 | `tests/rubrics.toml` 与 `rubrics.json` 的 R27 改为“退出回报口径披露正确”：必须识别材料未提供退出参数、绝对退出回报待核实；如有数值须标为条件分析；若采用演示性条件情景，则数值须落入原容差。条数 36、权重 7、`S_max = 220` 不变 | `check_rubrics.py` PASS；`check_package.py` #4b 双文件 36 条一致 |
| 3【待改】先修订后重判 | 业务输入与题面不变，四执行体均复用现有原生 `output/` 与轨迹，仅按修订后的判据重跑 verifier；不伪造、不补填新 agent 产物 | 四场 `criteria_counted=36`、`verifier_error=0`；`summary.json` 记录 fix6 四场为 invalid_runs 留痕 |
| 1/4【正确】其他项 | 未改题面、输入、PNG 路径、包结构与状态字段；继续仅回填主报告，不上传机器原报告、检查明细或修订说明附件 | 静态门禁与在线附件核验通过 |

**第五轮分数**：oracle `{scores['oracle']:.6f}`；qwen `{scores['qwen3.8-max-0902']:.6f}`；gpt `{scores['gpt-5.6-sol']:.6f}`；opus `{scores['claude-opus-4-8']:.6f}`；三模型均分 `{mean:.6f}`，门禁 `{summary['gate_pass']}`，难度 `A1`。

**改动判据**：仅 `R27` 一条（退出回报固定事实基准 → 信息不足/条件分析双路径），其余 35 条、权重、负向标记与 `S_max = 220` 未变。

**重跑方式**：WSL Ubuntu 独立 Docker Engine，镜像 `fin3-wkn-150:local`，judge `qwen3.7-plus`，claude-code 2.1.114；复用现有原生候选交付物，不重跑 Agent。
"""
    if "## 11. 第五轮整改记录" not in text:
        marker = "\n---\n\n*文档生成："
        if marker not in text:
            raise SystemExit("footer marker missing")
        text = text.replace(marker, section_11 + marker, 1)

    if not APPLY:
        print(text[-5000:])
        print("DRY RUN")
        return 0
    DOC.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {DOC} ({DOC.stat().st_size} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
