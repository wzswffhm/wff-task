---
name: rl01-data-production
description: 构造、迭代与质检 RL0-1 的**专项数据**（skill / tool / workflow）题包——按 Skill Discovery / Skill Generation·Editing / Skill Dependency / Dependency-aware Workflow / Subagent Workflow / MCP Scaling 六类能力方向出题，产出 instruction.md、真实参考文件、参考答案、rubrics.json 与 Harbor 题包（task.toml/metadata/artifacts），把 rubrics.json 落成 tests/rubrics.toml，跑分定难度档，并做配额分布与验收门禁检查。用于 RL0-1 数据生产的专项数据出题、功能型 Skill 设计、打分项（rubrics）设计、题包交付验收与甲方返修；不用于 weakness 驱动的数据（见独立 skill weakness-data-construction）、普通前端 rubrics 评分、Windows 专项评测题或纯 Harbor 运行排障。
metadata:
  source-docs: "20260913外发版-基于weakness和skill+的数据构造方案；RL0-1-数据生产规范GuidelineV1.1--20260920 for外部供应商；外发版-评测题包交付规范（rewardkit）20260913"
  scope: "仅专项数据（skill / tool / workflow）；weakness-driven 数据在独立 skill weakness-data-construction"
  version: "2.1"
---

# RL0-1 数据生产（专项数据：skill / tool / workflow）

把某一条能力方向做成系统性、完整覆盖的评测题包：覆盖不同场景、难度、环境和任务形态。
先判断当前在做哪一步，再读对应的参考文件，不要一次性加载全部。

> **范围**：本 skill 只负责 **专项数据 1000 条**（Skill Discovery、Skill Generation/Editing、
> Skill Dependency、Dependency-aware Workflow、Subagent Workflow、MCP Scaling）。
> **weakness-driven 数据不在这里**，见独立 skill `weakness-data-construction`。

## 模式选择

| 当前工作 | 读什么 |
|---|---|
| 出单题：题面、参考文件、参考答案、打分项 | 本文件 + [references/design-patterns.md](references/design-patterns.md) |
| 高经济价值题、法律案件复盘、多文件对账，或实跑分数明显过高 | [references/high-value-difficulty.md](references/high-value-difficulty.md)；再按需读出题与计分参考 |
| 规划批次：领域/复杂度/难度配额与五类专项分布 | [references/taxonomy-and-quota.md](references/taxonomy-and-quota.md) |
| 写或修订打分项 | [references/rubrics-spec.md](references/rubrics-spec.md) |
| 把 rubrics.json 落成 Harbor 能读的 tests/rubrics.toml | [references/rewardkit-conversion.md](references/rewardkit-conversion.md) |
| 估分、定难度档、按门槛补条或调权重 | [references/scoring-and-difficulty.md](references/scoring-and-difficulty.md) |
| 拼题包：task.toml、environment、tests、solution | [references/task-package-format.md](references/task-package-format.md) |
| 甲方返修、重跑判分、打包提交 | [references/revision-and-qc.md](references/revision-and-qc.md) |
| 质检、验收、待确认项 | [references/acceptance-and-open-items.md](references/acceptance-and-open-items.md) |

## 不可突破的硬约束

- **能力方向覆盖**：1000 条按五类各 200 条分布——Skill Discovery / Skill Generation·Editing /
  Skill Dependency / Dependency-aware Workflow / Subagent Workflow；MCP Scaling 低优、不单独占配额。
- **环境优先**：优先让环境本身变复杂（多工具、陌生 schema、必须依赖的 Skill、有状态长链路），
  而不是继续堆简单的整体任务。每条专项数据都要在题面里给出当前 Environment 下模型可用的工具集合 / MCP。
- **Skill 不可省略**：Skill 里必须承载特有信息或行为规则（特殊业务规则、环境特化 SOP、特殊阈值与
  内部映射、业务优先级、fallback 顺序），并能直接影响 final answer；否则它只是可有可无的 contextual document。
- **字段约束**：`skill_set` 与环境内 `environment/skills/<name>/` 逐一对应（可含干扰项）；
  `expected_skill_dependencies` 必须是 `skill_set` 的子集，Skill Discovery 场景必须**严格小于** `skill_set`。
- 难度：单题满分归一化 1.0。参考解得分须 > 0.85；三个模型（gpt-5.6-sol / claude-opus-4-8 / qwen3.8-max0902，claude-code 框架，裁判 qwen3.7-plus，各跑 1 次）平均分须 < 0.7，且至少一个模型非零——禁止全 0 的"死题"。
- 难度档由实测均值决定，不是申报值：A1 `0.6≤x<0.7` / A2 `0.5≤x<0.6` / A3 `x<0.5`，且**档位绑条数下限**（法律领域 简单≥25 / 中等≥30 / 复杂≥35）。落档后回填 `task.toml` 的 `difficulty`、`keywords`、`tags`。
- 打分项：`weight` 只能取 `{+10, +7, +3, -3, -7, -10}`；每题至少 2 条 `+10`；内容质量维度的正分合计 ≥ 全部正分的 30%；不要用 `+3` 堆叠——关键结论/指令/规范给 10，重要补充依据/专业规范/论证理由给 7。`-10` 只用于重大专业错误、幻觉、业务安全或合规风险。
- 扣分项至少 2 条且使用不同分值；每条须有输入材料支持的触发条件和可观察错误，不得与正分项重复惩罚同一缺陷。高分返修先看轨迹中的真实失误和简单送分项占比，见 [references/high-value-difficulty.md](references/high-value-difficulty.md)。
- 扣分项落地：`tests/rubrics.toml` 里**只能**写 `negate = true` + 正 weight，绝不写负 weight，也不要把扣分条改写成"未违规得分"的正向条。
- likert 标度唯一：只保留 `评分为 1–5 整数：5=… 1=…`，锚点唯一来源是 `rubrics.json` 的 `levels`；`levels` 必须与条目设计意图一致（历史上出现过整体错位一档）。
- 交付完整性：`跑分产物与轨迹/`（每个执行体的交付物 + agent 轨迹 + `reward.json` + `reward-details.json`）必须随包；`solve.sh`/`test.sh` 必须 LF + 0755。
- 真实性：参考文件必须是真实数据；不得要求模型凭猜测写法规条款、政策口径、职责分工或统计数据。参考答案须与题面规定的交付物类型、文件名、数量严格一致。
- 题面：任务说明、产出要求、硬约束（禁止项、文件名要求）各用独立段落显式写出，不得藏在括号里；用 Skill 的题目必须显式写明"必须通过该 Skill 完成，不得用其他方式"。
- 配置：`JUDGE_` 前缀变量只写在 `[verifier.env]`，严禁出现在 `[environment.env]`。
- 不得 hack：靠题面歧义、无法验证的要求或互相矛盾的约束刷低分，人工质检一经发现直接打回。

## 标准流程

1. **定能力方向**：本批要补哪一类（Discovery / Generation·Editing / Dependency / Workflow），配额还剩多少。
2. **设计不可省略点**：Skill 里放哪条特有规则/阈值/SOP，缺了它任务必然做不对。
3. **出题**：题面（含可用工具集合 / MCP 声明）+ 真实参考文件 + 参考答案（对照 design-patterns）。
4. **写判据**：`rubrics.json`（含负 weight、含 `levels`），按 rubrics-spec 自检。
5. **落成 Harbor 格式**：`python scripts/gen_rubrics_toml.py <task-dir>`；`tests/prompt.md` 用 rewardkit 模板原文。
6. **串行跑分与迭代（逐档放行，禁止多档齐开）**：详见
   [references/run-and-iterate.md](references/run-and-iterate.md)。四档顺序固定，每档必须
   同时满足门槛才放行下一档：
   - ① 跑 **oracle**（`harbor run -p <批次目录> -a oracle -n <题数>`）：参考分须 **> 0.85**；
   - ② 合格后跑 **qwen3.8-max-0902**：三题均值须 **< 0.7**；
   - ③ 合格后跑 **claude-opus-4-8**：均值须 **< 0.7**，且**原则上应高于 qwen**（同名模型族之间的
     相对表现要能解释；opus 反而低于 qwen 时先查判官波动与题目歧义，再决定是否放行）；
   - ④ 合格后跑 **gpt-5.6-sol**：均值须 **< 0.7**。
   任一档不达标 → 停下，按下面第 7 步改判据后**重跑该档**，不要往下走。
7. **不达标时的整改优先级与一致性校验**：先改 `rubrics.json`（合并/拆分/调权重/收紧或放宽档位描述）；
   只有在确有必要时才动参考答案，**题面与参考答案能不动就不动**。每次改完判据**必须**重跑该档判分
   （agent 产物可沿用，见 [references/revision-and-qc.md](references/revision-and-qc.md) 第二节），
   并跑 [scripts/check_rubric_grounding.py](scripts/check_rubric_grounding.py) 校验
   **「判据不得要求题面没有的东西」**：每条 criterion 的要求都要能在 `instruction.md`
   （或题面明确要求遵守的 `environment/skills/` 规范）里找到依据；找不到就必须删掉该条，
   或先把要求补进题面（补题面 = 题面变更，该档 agent 必须重跑）。
8. **定档回填**：按实测均值落 A1/A2/A3，补足该档条数下限，同步 `task.toml` 的
   `difficulty` / `keywords` / `tags`。
9. **打包提交**：`<批次目录>/<题目目录>/五件套 + 跑分产物与轨迹/`，附 `交付文档.md`。
   跑分产物须含**每个执行体的原生 agent 轨迹**（harbor + claude-code 产出的
   `trajectory.json` / `claude-code.txt`），参考解（oracle）不需要轨迹。

改动判据、权重或参考答案后必须重跑判分（可只重跑判官，见
[references/revision-and-qc.md](references/revision-and-qc.md) 第二节）。

## 产出与自检

```bash
python scripts/gen_rubrics_toml.py <task-dir>          # rubrics.json → tests/rubrics.toml
python scripts/validate_rubrics.py <task-dir> [...]    # 判据门禁 + json/toml 一致性 + 锚点一致性
python scripts/validate_task_package.py <task-dir>     # 题包字段、权重、分布、skill_set 约束
python scripts/check_batch_quota.py <批次表或 task.toml 目录>
python scripts/rejudge_by_docker.py <task-dir> <镜像> <执行体>=<交付物目录> [...]
```

这些脚本只覆盖可机械判定的门禁（字段、权重、分布、配额、锚点、格式）。题目真实性、
"Skill 是否真的不可省略"、参考答案是否专业正确，仍须人工判断。

## 缺失信息处理

文档未给出的信息（三级/四级标签知识体系、平台环境模板名、MCP 能力清单）一律标 `TBD` 并写明来源，
不要臆造。已知冲突与默认口径见 [references/acceptance-and-open-items.md](references/acceptance-and-open-items.md)；
rewardkit 与本文档的口径差异（rubrics.json 位置、`/logs/artifacts/output`、负 weight 表达）
以 rewardkit 为准，详见 [references/rewardkit-conversion.md](references/rewardkit-conversion.md)。
