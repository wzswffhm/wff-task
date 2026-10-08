# 专项数据出题套路

## 从 Task Distribution 转向 Environment Distribution

当前 Cowork RL 数据的通病：任务多跑在相对简单的环境里（以 filesystem / shell / 少量原生工具为主）；Tool schema、可用能力和调用方式相对固定；Skill 即使存在也只是辅助信息，并非完成任务所必需；Workflow 多是线性"读取 → 处理 → 输出"，缺少真实业务中的状态变化、异步依赖、异常恢复和跨工具协同。

下一阶段的重点是扩充 Environment Distribution。构造时优先让环境本身变复杂：多工具、陌生 schema、必须依赖的 Skill、有状态的长链路。

## 任务描述

自然语言描述任务场景、需要用到的材料、交付物要求。三块内容各自独立成段显式写出，不得藏在括号里：

1. 任务说明。
2. 产出要求。
3. 硬约束：禁止项、文件名要求等。

## Skill 专项

### Skill Discovery（200 条）

提供多个 Skill，要求模型自行判断：是否需要 Skill，以及应该使用哪个 Skill。用 `skill_set` 放环境内安装的功能型 skill（含干扰项），`expected_skill_dependencies` 严格小于 `skill_set`。

### Skill Generation / Editing（200 条）

创建 Skill；修改已有 Skill；从 SOP 抽取 Skill；Skill migration；Skill package repair。

### Skill Dependency（200 条）——三种推荐构造方式

| 类型 | 构造方式 | 失败表现 |
|---|---|---|
| 一：特殊业务规则 | Skill 明确规定：当两个 authoritative source 的关键字段冲突时，禁止自行选择，必须暂停并向用户确认。Task 中主动埋入这种冲突 | 模型没真正遵循 Skill，最终一定会进入错误 branch |
| 二：环境特化 SOP | Skill 定义企业内部审批流程，如 Draft → Compliance Review → Manager Approval → Publish；Task 要求完成发布 | 模型走 Draft → Publish 时，最终 Workflow State 必须失败 |
| 三：特殊计算 / 判定规则 | Skill 中包含特殊阈值、内部映射规则、自定义字段定义、业务优先级、fallback 顺序，并直接决定 final answer | 缺少 Skill 中的特殊知识/行为规则时，模型很难正确完成任务 |

## Workflow 专项

### Dependency-aware Workflow（200 条）

任务中存在明确 dependency：

```text
A → B
A → C
B + C → D
D → Final
```

要求模型正确拆解 dependency、维护哪些任务已完成、避免提前执行依赖未满足的步骤、Final 前确认 dependency 已全部完成。

### Subagent Workflow（200 条）

构造必须依赖多个 Subagent Result 才能完成 Final 的任务。最好是在 codex 等框架下运行该任务会真正触发 subagent。

## MCP Scaling（低优）

扩大模型在非原生工具、陌生 Tool Schema 和不同 Tool 组合下的泛化能力，主要可通过 MCP 实现。数据需基于各 Agent Framework 可接入的 Plugin / MCP 能力构造，并在每条任务中明确提供当前 Environment 下模型可使用的工具集合 / MCP。工具可以是框架已有能力，也可以是动态注入的自定义工具（在题目里显式说明）。

## 参考文件与参考答案

- 参考文件：该任务场景下真实的交付物是什么，就用什么源文件（CSV、PDF、合同、日志等）。必须为真实数据；不得要求模型凭空猜测法规条款、政策口径、职责分工或统计数据。数量不限，总大小 20GB 以内。
- 参考答案：由领域专家产出，与题目标注中规定的交付物类型、文件名、数量严格一致，经打分项判分后须满足 `score_final ≥ 0.85`；低于则修正。

## 出题时要顺手确认的事

1. 这条数据落在哪个一级/二级领域，是否撞了已出题的知识点或 workflow（同一知识点 ≤2 道）。
2. `task_complexity` 按硬指标（文件数、Requirement 数、产物数、evidence hop、执行步数、工具种类）核出来，而不是凭感觉。
4. 交付物名字、路径、数量是否在题面、`artifacts`、`[[metadata.deliverables]]`、参考答案四处一致。
5. 打分项是否满足分布要求（≥2 条 +10、内容质量正分 ≥30%），以及是否覆盖了该交付物类型必须覆盖的维度。
