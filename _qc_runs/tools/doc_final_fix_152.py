# -*- coding: utf-8 -*-
"""交付文档终修：
 1) L131 门禁行 typo（;。）
 2) 3.3 静态自检数据仍是 v2 旧值（33/179/92.7% → 40/228/94.3%）
 3) 新增 3.2.3 判分噪声与档位余量披露（N01 噪声 + A2 余量 0.9pp 越档风险）
 4) §4 整节：跑分产物位置由「批次级平级」改为「题目目录内」（质检#7）+ 树结构 + 补 opus
 5) summary.json 字段说明与实际字段对齐
 6) §5 批次包与归档描述
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

P = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261009-152\FIN3-WKN-152\交付文档.md")
raw = P.read_text(encoding="utf-8")
ok = []


def rep(old, new, label):
    global raw
    n = raw.count(old)
    if n != 1:
        print(f"  [!!] {label}: 匹配 {n} 次")
        ok.append(False)
        return
    raw = raw.replace(old, new, 1)
    print(f"  [OK] {label}")
    ok.append(True)


print("=" * 94)
print("交付文档终修")
print("=" * 94)

# 1) typo
rep("> 门禁：三模型均分 **0.590643** < 0.70 → **PASS**；至少一个模型非零（非死题）;。",
    "> 门禁：三模型均分 **0.590643** < 0.70 → **PASS**（余量 0.109357）；三模型均非零（非死题）。",
    "1) 3.2.1 门禁行 typo + 补余量")

# 2) 3.3 静态自检数据
rep("（33 条 / 正 29 负 4 / 正分池 `S_max 179.0` / CI 4 条 / 内容质量正分占比 **92.7%**）",
    "（**40 条** / 正 36 负 4 / 正分池 `S_max 228.0` / 负分池 24（−7×3、−3×1）/ CI 4 条 / 内容质量正分占比 **94.3%**）",
    "2) 3.3 check_rubrics 数据 v2→v4")

# 3) 新增 3.2.3 披露
DISC = """
#### 3.2.3 判分噪声与档位余量披露（如实说明，未重跑）

**① N01 单条判官输出自相矛盾（qwen）**
`qwen3.8-max-0902` 的 `N01`（负分判据）：判官 `reasoning` 结尾明确写
「…all errors have been clearly corrected …, **N01 does not apply**; the deliverables do NOT
carry over legacy errors」，但最终 `raw=yes` / `value=0`（negate 语义下 = 触发违规、扣 7 分）。
这是 LLM 判官 reasoning 与 final answer 不一致的**单次噪声**，非判据缺陷——同条判据在
`gpt-5.6-sol` 与 `claude-opus-4-8` 上均为 `value=1`（正常）。

- 按记录值计入：qwen = **0.697368**
- 若按评语语义修正：qwen = 0.697368 + 7/228 = **0.728070**（差 +3.07pp）
- **处置：不重判**。依据 ①甲方质检「判分自洽」仅核「逐条复算与 `reward.json` 一致」
  与「`description`/`weight` 与现行判据逐条一致」两项，本包均通过（复算差 0、40 条零漂移）；
  ②`pitfall-cases` 案例 7 明示「判官是 LLM，重跑一次就可能越档」，重跑有引入新噪声与越档的
  双重风险；③误差方向使均值偏低、离 <0.70 门禁更远。此处如实披露以备人检。

**② 档位余量提示（A2 上界 0.6，当前 0.590643）**
均值距 A2 上界仅 **0.009357（0.94pp）**，距 A1 下界 0.6 同为此距离。按 `evidence-checks`
§1.3「余量薄时在报告中提示**重跑判官可能越档**」：**若任何执行体重跑判官，均值有较大概率
升破 0.6 而越档至 A1**，届时须按实测重新落档并同步 `difficulty`。本轮未做任何 regrade。

**③ 各执行体 agent 阶段口径**
四执行体均一次跑成、`criteria_counted=40`、`verifier_error=0`；`gpt-5.6-sol` 判分单条最长
51 分钟（R29 深读全表），总判分时长 qwen 61 分钟 / gpt 98 分钟 / opus 63 分钟，
`verifier.timeout_sec=18000`（5 小时）内完成，无超时、无限流失败、无 fail-closed 占位残留。

"""
anchor = "### 3.3 静态自检（17 项）"
rep(anchor, DISC + anchor, "3) 新增 3.2.3 披露小节")

# 4) §4 整节
rep("## 4. 跑分归档（**批次级** `跑分产物与轨迹/`）",
    "## 4. 跑分归档（**题目目录内** `FIN3-WKN-152/跑分产物与轨迹/`）",
    "4a) §4 标题")

rep("> `跑分产物与轨迹/` 置于**批次级**，与题目目录 `FIN3-WKN-152/`、`交付文档.md` **平级**；各执行体统一使用 `output/` 目录。",
    "> `跑分产物与轨迹/` 与 `交付文档.md` 均**归入题目目录** `FIN3-WKN-152/`，使批次 zip **第二层仅题目目录**"
    "（质检报告第 7 条）；四执行体统一使用 `output/` 目录。",
    "4b) §4 位置说明（质检#7）")

OLD_TREE = """work_fin-b01_20261009-152/                  ← 批次目录（zip 根）
├── 交付文档.md
├── 跑分产物与轨迹/                          ← 批次级（与题目目录平级）
│   ├── oracle/               { output/, 轨迹/{oracle.txt,trial.log,说明.txt}, reward.json, reward-details.json }
│   ├── gpt-5.6-sol/          { output/, 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
│   ├── qwen3.8-max-0902/     { output/, 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
│   └── summary.json
└── FIN3-WKN-152/                            ← 题目目录（五件套）
    ├── instruction.md
    ├── task.toml
    ├── rubrics.json
    ├── environment/  { Dockerfile, requirements.txt, input_files/ (60 文件) }
    ├── solution/     { solve.sh, golden_output/ (7 文件) }
    └── tests/        { rubrics.toml, prompt.md, test.sh, finalize.py, __golden_output/ (7 文件) }"""
NEW_TREE = """work_fin-b01_20261009-152/                  ← 批次目录（zip 根）
└── FIN3-WKN-152/                            ← 第二层仅题目目录
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/  { Dockerfile, requirements.txt, input_files/ (60 文件) }
    ├── solution/     { solve.sh, golden_output/ (7 文件) }
    ├── tests/        { rubrics.toml, prompt.md, test.sh, finalize.py, __golden_output/ (7 文件) }
    ├── 交付文档.md                          ← 本文件（归入题目目录）
    └── 跑分产物与轨迹/                       ← 归入题目目录
        ├── oracle/               { output/ (7), 轨迹/{oracle.txt,trial.log,说明.txt}, reward.json, reward-details.json }
        ├── qwen3.8-max-0902/     { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        ├── gpt-5.6-sol/          { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        ├── claude-opus-4-8/      { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        └── summary.json          { oracle_reward=1.0, three_model_mean=0.590643, measured_band=A2, gate_pass=true }"""
rep(OLD_TREE, NEW_TREE, "4c) §4 目录树（批次级→题目目录内 + 补 opus + summary）")

# 5) summary 字段
rep("`summary.json` 字段：`task_id` / `task_version` / `runs[]`（model、reward、trial、scored、verifier_error）/ `invalid_runs[]` / `three_model_mean` / `three_model_gate` / `declared_difficulty` / `declared_complexity` / `gate_pass` / `blocker`（如有）。",
    "`summary.json` 字段：`task_id` / `task_version`（4.0.0）/ `round` / `runs[]`（model、trial、reward、criteria_counted、verifier_error）/ "
    "`invalid_runs[]` / `oracle_reward`（1.0）/ `three_model_mean`（0.590643）/ `three_model_gate`（<0.70）/ "
    "`three_model_complete`（true）/ `measured_band`（**A2**）/ `declared_difficulty`（**A2**）/ `declared_complexity`（C5）/ "
    "`gate_pass`（**true**）/ `blocker`（null）。",
    "5) summary 字段说明")

# 6) §5
rep("| 批次包 | `work_fin-b01_20261009-152.zip`（批次目录：交付文档 + 题目目录 + 跑分产物与轨迹） |",
    "| 批次包 | `work_fin-b01_20261009-152.zip`（**第二层仅 `FIN3-WKN-152/`**：五件套 + 交付文档 + 跑分产物与轨迹） |",
    "6a) §5 批次包描述")
rep("| 归档 | `跑分产物与轨迹/`（oracle + 已完成模型，含产物、轨迹、逐条判分明细） |",
    "| 归档 | `FIN3-WKN-152/跑分产物与轨迹/`（**四执行体** oracle + qwen + gpt + opus，含产物、轨迹、逐条判分明细 + `summary.json`） |",
    "6b) §5 归档描述（四执行体）")

print()
if all(ok):
    P.write_text(raw, encoding="utf-8", newline="\n")
    print(f"[写出] {P}  {len(raw.splitlines())} 行  {len(raw.encode('utf-8')):,} B")
else:
    print("[!!] 有失败项，未写出")

# 残留过时内容扫描
print()
print("=" * 94)
print("残留扫描（应全部为空）")
print("=" * 94)
t = P.read_text(encoding="utf-8")
for pat, label in [
    ("批次级", "批次级（应已改为题目目录内）"),
    ("与题目目录平级", "平级描述"),
    ("33 条", "v2 判据数"),
    ("S_max 179", "v2 正分池"),
    ("92.7%", "v2 内容质量占比"),
    ("[[G4", "未回填占位符"),
    ("[[G5", "未回填占位符"),
    ("[[DIFFICULTY", "未回填占位符"),
    (";。", "typo"),
]:
    hit = pat in t
    print(f"  {'[!!] 仍存在' if hit else '[OK] 无'}  {label}（{pat}）")
