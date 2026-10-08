---
name: weakness-qc
description: 质检 weakness-driven RL0-1 题包（金融/办公 Cowork 场景）：跑机器门禁、复算判分证据、从输入材料独立重算关键链路、排查"难度被口径歧义撑着"、核结构与打包，产出逐条可溯源的质检报告与整改单，给出通过 / 不通过结论。用于 weakness 题包的 AI 质检、人检前预检、甲方返修复检；不用于出题与返修落地（见 weakness-data-construction）、通用专项数据质检（见 rl01-task-qc）、前端 rubrics 评分或纯 Harbor 排障。
metadata:
  scope: "只质检与开整改单；改题与返修落回 weakness-data-construction"
  upstream: "weakness-data-construction（生产侧，机器门禁脚本以它为准）；rl01-task-qc（通用 RL0-1 题包质检）"
  version: "1.0"
---

# weakness 题包质检

判定一条 weakness 题包**能不能交付**，并给出可复检的整改单。

**默认只读**：不修改题包里的任何文件；用户明确要求"顺手改"时才动手，且改动判据/权重/金标/材料后
必须按「重跑决策」重跑。

## 这个 skill 存在的理由

机器门禁只能回答"字段对不对"。weakness 题包被打回的真实原因几乎都是**判断类问题**：

- 判据的口径/换算在输入材料里找不到**唯一**出处，或材料自相矛盾；
- 难度其实是**题面歧义**撑起来的（锁死口径模型就会做对，档位当场失效）；
- 金标自己的列示过程与结论不自洽，判据却按 ±0.01 锚死；
- 门禁脚本的机械映射与规范原文冲突，被误当成"题包标错了"。

本 skill 把这几类固化成必查项、脚本与实证案例。

## 模式选择

| 当前工作 | 读什么 |
|---|---|
| 全量质检（默认） | 本文件，按需读下面四个 reference |
| 跑门禁；脚本与规范冲突怎么处理 | [references/gates.md](references/gates.md) |
| 判分复算、独立重算、结构与安全检查 | [references/evidence-checks.md](references/evidence-checks.md) |
| 判断"是不是口径歧义撑着难度"；看历史踩坑案例 | [references/pitfall-cases.md](references/pitfall-cases.md) |
| 写报告、定结论、给重跑建议 | [references/report-template.md](references/report-template.md) |

## 不可突破的硬规则

1. **默认只读**。问题写进报告与整改单，不擅自改题包。
2. **结论只分三档，措辞不许含糊**：必须整改 / 提示（**明确写"不构成退回理由"**）/ 已核实通过。
   没问题就判通过——**不要鸡蛋里挑骨头**：归档习惯、可选加固、措辞优化一律进"提示"，
   并说清它为什么不影响验收。
3. **每条问题给证据三件套**：位置（文件 + 条目号/段落）、原文引用、判定依据（引规范或材料原句）。
   只写"建议优化""可以更好"不构成质检结论。
4. **判据锚点必须能在 `environment/input_files/` 找到唯一出处**。材料自相矛盾 ≠ 难度，
   按**必须整改**报，并给出"锁口径 / 放宽判据 / 保留现状（需甲方确认）"三条处置路径。
5. **脚本 FAIL 不等于题包有错**。先跑脚本自检，再回规范原文逐列核对；脚本与规范冲突时
   **以规范原文为准**，报告里单列「脚本口径与规范冲突」小节（附脚本原始输出 + 人工判据），
   **不得据此把题包判成不通过**。详见 [references/gates.md](references/gates.md) 第三节。
6. **难度不能被口径歧义撑着**：三个执行体在同一组判据上**一致失分**、且该组权重 ≥ 正分池 25% 时，
   先按口径歧义排查，并**预估锁口径后的分数变化与档位风险**，再下结论。见
   [references/pitfall-cases.md](references/pitfall-cases.md) 案例 2。
7. **判分证据必须可复算**：逐条复算要与 `reward.json` 一致；`reward-details.json` 的
   description 与 weight 要与现行 `tests/rubrics.toml` 逐条一致——否则该轮判分不能作为难度证据。
8. **不许把未验证写成通过**。跑不了判分、缺产物、拿不到规范原文时标 `未验证` / `TBD`，
   写明由谁提供，并单列，不计入通过。

## 标准流程

1. **清点**：解包到独立目录（不要就地解压进题包）；看批次/题目/版本命名、五件套、跑分产物是否随包。
2. **机器门禁**：按 [references/gates.md](references/gates.md) 清单跑，**先 `--self-test` 再判定**，
   原始输出留档。
3. **核判分证据**：[references/evidence-checks.md](references/evidence-checks.md) 第 1 节——
   逐条复算、一致性核对、均值定档、轨迹框架核对、判断"重聚合"能否接受。
4. **独立重算关键链路**：同文件第 2 节——**不引用金标结论**，只读 `environment/input_files/` 自建计算；
   先找"卡点链路"（通常 1–3 条链决定大部分分值）。
5. **排查口径歧义与 hack**：[references/pitfall-cases.md](references/pitfall-cases.md) 逐条过，
   算集中度、追问"口径能否唯一推出"。
6. **核结构与安全**：[references/evidence-checks.md](references/evidence-checks.md) 第 3 节——
   权限位/LF/残留/密钥/执行体目录白名单/脱敏边界。
7. **出结论与整改单**：按 [references/report-template.md](references/report-template.md) 写，
   **一题一个 md**，落到 `outputs/`，**不要写进题包目录**（会污染交付包）。
   每条整改动作必须标注**是否需要重跑**。
8. **复检**：返修包只复检"有问题条目 + 受影响条目 + 全部机器门禁"，并确认没引入新问题。

## 重跑决策（一句话版）

| 改了什么 | 要跑什么 |
|---|---|
| `task.toml` 元数据（复杂度档/标签/难度）、`.md` 文档、证据文件归位 | **不用跑** |
| 判据 description/权重、金标数值 | **只重跑判官**（`rejudge_by_docker.py`），agent 产物沿用 |
| `instruction.md` 或 `environment/input_files/` | **必须重跑 agent 三执行体 + 判官 + 重定难度档** |
| 把判据放宽到"模型答案也算对" | 分数会大涨：先按「该组权重 ÷ 正分池」预估是否破 0.7，破档需同步补难度 |

命令与两个必踩的坑（代理变量、判分残留 `__pycache__`）见
[references/report-template.md](references/report-template.md) 第四节。

## 与其它 skill 的关系

- **出题 / 返修落地**：`weakness-data-construction`（生产侧；机器门禁脚本以它为准）。
- **通用 RL0-1 题包质检**（专项数据等）：`rl01-task-qc`。
- 本 skill 只做 weakness 题包的质检与整改单，不替生产侧改题；发现的问题回给生产侧执行。
