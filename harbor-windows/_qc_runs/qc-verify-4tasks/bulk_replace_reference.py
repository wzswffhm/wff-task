# -*- coding: utf-8 -*-
"""对甲方参考包 _reference/windows-harbor-qc 的文档执行规则更新替换。

规则：1) task.toml 可不写 docker_image；2) GLM/Kimi 不再运行；
      3) 满分平局时按逐 testcase 通过数判定（Qwen 更少即通过）。
旧规则直接删除，不做保留说明。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc"

R = [
    # ---------- references/checklist.md ----------
    ("references/checklist.md",
     "（**2026-10-13 起：必需 12 个**；含可选 GLM/Kimi 为 14 个）",
     "（Qwen 3、Opus 3、Oracle 3、NOP 3，共 12 个）"),
    ("references/checklist.md",
     "- GLM-5.3：1 次（**自 2026-10-13 起可选**）；\n- Kimi K3：1 次（**自 2026-10-13 起可选**）。\n",
     ""),
    ("references/checklist.md",
     "8 次模型运行必须全部 `VALID`",
     "6 次主模型运行（Qwen 3 + Opus 3）必须全部 `VALID`"),
    ("references/checklist.md",
     "唯一例外是 8 次模型运行全部有效且全部为 0",
     "唯一例外是 6 次主模型运行全部有效且全部为 0"),
    ("references/checklist.md",
     "GLM/Kimi 不参与主模型分差，GLM 1 而 Opus 0 本身不触发返修，但要纳入全模型结果分布分析；缺少规定 job",
     "GLM/Kimi 不再运行，不参与主模型分差；历史归档中 GLM 1 而 Opus 0 本身不触发返修。缺少必备 job"),
    ("references/checklist.md",
     "- 规定的 8 次模型运行全部 `VALID/0`，因此 Opus 0 = Qwen 0。",
     "- 6 次主模型运行全部 `VALID/0`，因此 Opus 0 = Qwen 0。"),
    ("references/checklist.md",
     "固定的 14 个原生 Harbor job 仍是标准目录硬门禁；缺任一规定 job 应写成目录/原始证据缺件。",
     "12 个原生 Harbor job 仍是标准目录硬门禁；缺任一必备 job 应写成目录/原始证据缺件。"),
    ("references/checklist.md",
     "- GLM 为 1、Opus 为 0；GLM 不参与 Opus/Qwen 主分差。",
     "- 历史归档中 GLM 为 1、Opus 为 0；GLM/Kimi 不再运行，不参与 Opus/Qwen 主分差。"),
    # ---------- references/manual-review.md ----------
    ("references/manual-review.md",
     "| 全模型区分度：已分析 Qwen/Opus/GLM/Kimi 全部规定运行；Opus 总分严格高于 Qwen，或总分相等（含双方三次全满分）时 `testcase_pass_sum` 严格更高；",
     "| 主模型区分度：已分析 Qwen 与 Opus 各三次运行；Opus 总分严格高于 Qwen，或总分相等（含双方三次全满分）时 Opus 的 `testcase_pass_sum` 严格更高（Qwen 通过的 testcase 更少即成立）；"),
    ("references/manual-review.md",
     "| 8 个模型 job 均逐份检查",
     "| 6 个主模型 job 均逐份检查"),
    ("references/manual-review.md",
     "8 份模型轨迹",
     "6 份主模型轨迹"),
    # ---------- references/quality-gates.md ----------
    ("references/quality-gates.md",
     "必须分析 Qwen、Opus、GLM、Kimi 的全部规定运行，而不是只看一轮",
     "必须分析 Qwen 与 Opus 的各三次运行，而不是只看一轮"),
    ("references/quality-gates.md",
     "`VALID/1`、正式分已顶格的过易满分情形**——必须由相同 required testcase 集合上的\n`testcase_pass_sum` 严格打破平局，否则 `FAIL`。",
     "`VALID/1`、正式分顶格的情形**——由相同 required testcase 集合上的\n`testcase_pass_sum` 判定：Opus 严格更高即通过（**Qwen 通过的 testcase 比 Opus 少也是可行的**），否则 `FAIL`。"),
    ("references/quality-gates.md",
     "但不再单独否决。GLM/Kimi 不参与主分差，\n但必须用于检查整体结果分布、异常和证据完整性。",
     "但不再单独否决。GLM/Kimi 不再运行，不参与主分差，也不参与判定。"),
    # ---------- references/procurement-manual-integration.md ----------
    ("references/procurement-manual-integration.md",
     "当前标准 Task 根目录和 14 个直接 Harbor jobs",
     "当前标准 Task 根目录和 12 个直接 Harbor jobs"),
    # ---------- README.md ----------
    ("README.md",
     "它检查直接 Harbor Task 根目录和 14 个原始 job",
     "它检查直接 Harbor Task 根目录和 12 个原始 job"),
    ("README.md",
     "    <GLM 一个 Harbor job>\n    <Kimi 一个 Harbor job>\n",
     ""),
    ("README.md",
     "`model-gate.json`：3/3/1/1 模型运行和准入结果；",
     "`model-gate.json`：3/3 主模型运行和准入结果；"),
    ("README.md",
     "规定的 8 次模型运行全部 `VALID/0` 时仍允许零分平局；",
     "6 次主模型运行全部 `VALID/0` 时仍允许零分平局；"),
    ("README.md",
     "`model-jobs.json`：14 个 Harbor job",
     "`model-jobs.json`：12 个 Harbor job"),
    ("README.md",
     "、GLM 1 而 Opus 0，都不能单独触发返修",
     "、历史归档中 GLM 1 而 Opus 0，都不能单独触发返修"),
    ("README.md",
     "若 `jobs/` 缺少固定 14 个原生 Harbor job",
     "若 `jobs/` 缺少 12 个原生 Harbor job"),
    ("README.md",
     "脚本分析 Qwen×3、Opus×3、GLM×1、Kimi×1\n全部结果；Qwen 与 Opus 同时三轮满分时直接失败，8 次运行全部满分时明确标记为全模型满分题并\n拒收。未触发满分拒绝时，继续应用 Opus/Qwen 总分与 testcase 累计通过数规则。",
     "脚本分析 Qwen×3、Opus×3 全部结果（GLM/Kimi 不再运行）。先比较 Opus/Qwen 三次正式分数总和；\n总分相等时由相同 required testcase 集合上的 Opus `testcase_pass_sum` 是否严格更高判定——\nQwen 通过的 testcase 比 Opus 少即通过。仅当逐 testcase 通过数也完全相同（或 Opus 更低）时\n失败；6 次主模型运行全部 `VALID/0` 的零分平局例外保留。"),
    # ---------- SKILL.md ----------
    ("SKILL.md",
     "；GLM 1 次、Kimi 1 次**自 2026-10-13 起为可选**，存在时合计 14 个。",
     "。**GLM 与 Kimi 不再运行**，包内若带这两类轮次一律忽略。"),
    ("SKILL.md",
     "全部规定模型运行（必需口径 6 次；含可选 GLM/Kimi 则 8 次）均为 `VALID/0` 时",
     "6 次主模型运行均为 `VALID/0` 时"),
    ("SKILL.md",
     "GLM/Kimi 不参与主分差，GLM 高于 Opus本身不触发返修，但必须纳入全模型结果分布分析，且所有原始轨迹必须完整有效。",
     "GLM/Kimi 不再运行，不参与主分差；历史归档中 GLM 高于 Opus 本身不触发返修。所有原始轨迹必须完整有效。"),
    ("SKILL.md",
     "「Qwen 与 Opus 同时三轮满分」本身**不再**是出局理由（2026-10-12 放宽），但 required testcase 的条数与颗粒度必须真的能把两者分开。",
     "「Qwen 与 Opus 同时三轮满分」本身不是出局理由，只要 required testcase 的颗粒度能把两者分开即通过（**Qwen 通过的 testcase 比 Opus 少也算成立**）。"),
    ("SKILL.md",
     "全部规定模型运行均有效且全 0；泛化的“每模型运行次数不足”；GLM 为 1 而 Opus 为 0。",
     "6 次主模型运行均有效且全 0；泛化的“每模型运行次数不足”；历史归档中 GLM 为 1 而 Opus 为 0。"),
    ("SKILL.md",
     "`jobs/` 少于规定数量的原生 Harbor job（**2026-10-13 起为 12 个**；含可选 GLM/Kimi 的旧口径为 14 个），仍按目录/证据缺件判定失败。",
     "`jobs/` 少于 12 个原生 Harbor job，仍按目录/证据缺件判定失败。"),
    ("SKILL.md",
     "十项人工门禁之外还必须执行全模型区分度硬门禁：分析 Qwen、Opus、GLM、Kimi 的全部规定运行；\nQwen 与 Opus 同时三轮满分或 8 次模型运行全部满分时，题目过易，最终不得通过。",
     "十项人工门禁之外还必须执行主模型区分度硬门禁：分析 Qwen 与 Opus 的各三次运行。Opus 总分\n严格高于 Qwen 即通过；总分相等（含双方三次全满分）时，由相同 required testcase 集合上的\nOpus `testcase_pass_sum` 是否严格更高判定——Qwen 通过的 testcase 比 Opus 少即通过。仅当逐\ntestcase 通过数也完全相同（或 Opus 更低）时才判不通过；6 次主模型运行全部 `VALID/0` 的零分\n平局例外保留。"),
    ("SKILL.md",
     "- `PASS`：直接 Harbor 目录、测试、14 个 jobs、",
     "- `PASS`：直接 Harbor 目录、测试、12 个 jobs、"),
]

missed = 0
for rel, old, new in R:
    p = PKG / rel
    if not p.is_file():
        print("[缺失文件] %s" % rel)
        missed += 1
        continue
    text = p.read_text(encoding="utf-8")
    n = text.count(old)
    if n == 0:
        print("[未命中] %-52s %s" % (rel, old[:60].replace("\n", "\\n")))
        missed += 1
        continue
    p.write_text(text.replace(old, new), encoding="utf-8")
    print("[替换 %dx] %-46s %s" % (n, rel, old[:52].replace("\n", "\\n")))

print("\n共 %d 条规则，未命中 %d 条" % (len(R), missed))
sys.exit(1 if missed else 0)
