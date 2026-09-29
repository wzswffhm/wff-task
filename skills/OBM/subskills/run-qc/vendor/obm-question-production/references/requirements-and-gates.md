# OBM 需求与门禁

## 项目目的

OBM Source 项目不是收集现成 benchmark 答案，而是由有三年以上大型工程经验的领域专家，围绕目标 benchmark 已考察的领域或能力，原创同等难度且有训练价值的任务。每项交付由 proposal、可程序化验证思路、离线 sources 和解决核心难点的专家经验组成，用于验证专家经验是否能真实提升 agent 的解题能力。

目标 benchmark：`terminal_bench3`、`terminal_bench4`、`programbench`、`swe_marathon`、`deepSWE`、`froniterSWE`。最后一项是源文档给出的字面枚举，虽然疑似 `frontierSWE` 拼写错误，在接收端确认前不要自行纠正。

本批次以 `D:\hc\obm\Benchmark` 中的五个本地 `main.zip` 为权威版本，不要求 release tag 或远端 commit。用文件 SHA-256 标识实际输入版本。当前优先 `deep-swe-main.zip`；其用户确认配置和首候选见 [project-defaults.md](project-defaults.md)。

## 三种造题方式

- **A：现有/新建 Repo + 新需求。** 基于真实仓库原创历史上不存在公开方案的新功能、复杂缺陷、迁移、重构或 CI 任务，并设计行为级 verifier。
- **B：现有软件/System + 新目标。** 基于软件、模型、编译器或 ML baseline 原创新目标、约束、公开/隐藏 workload 及正确性或性能指标，适用于优化、重实现、AI for AI 等任务。
- **C：专家真实工作任务。** 选择现实有用、可程序化验证的代码任务，提供 Docker 形式环境；解题经验成为 skill，标准答案或其行为规范成为 verifier。

所有类型都禁止从已有 commit、PR、patch、公开 benchmark 答案或可直接检索到的 solution 倒推题目。

## 提案来源与用户后续确认

最新需求与用户确认允许 AI 协助或生成 `proposal.json` 自然语言内容。交付仍必须是人类可读、口语化、与真实 Source 和验证机制一致的工程说明；不能伪造真实专家资历、工时或独立验收。这里的 `expert_experience_skill` 是某一道题的专家经验文本，不是本目录中的 Codex 工作流 skill。

## Proposal 内容

每个 proposal 至少覆盖：

- 改造思路：对来源资源做了什么改造；C 类没有改造时可省略。
- 具体改造细节。
- agent 任务内容。
- 解题限制。
- 难点/能力考察点，分点列出并与专家经验逐项对应。
- 来源、真实应用场景、验证思路和专家经验。

用户已确认准确接收模板：`A_modification_idea`、`B_modification_details`、`C_agent_task`、`D_task_difficulties`。旧版 `D_solution_constraints` 不再单列，保留有用的限制于公开题面和 `C_agent_task`；旧 `E_task_difficulties` 转为 `D_task_difficulties`。不要把两套字段混在交付中。按接收方 Python 校验器核对所有四个字段、domain 前缀和关联题映射。

包名要求 `{bench_name}_{proposal_name}`，但 schema 没有 `proposal_name` 字段。把 proposal name 作为运行配置中的唯一 slug，不要私自给 `proposal.json` 增加字段。

## 首轮静态门禁

以下任一情况直接拒绝候选：

- proposal 自相矛盾、有事实错误或不存在可能解。
- 从公开 commit/PR、已有 patch 或公开 benchmark 解答倒推。
- 解法与已有 patch 高度相似。
- 只修改公开 benchmark 的名字或数字。
- verifier 只是复制已有 tests，没有独立行为验收和关键边界。
- verifier 依赖公开题面没有声明的固定 JSON 字段、返回层级、状态值、幂等摘要组成、异常类型或业务语义，导致解题者只能猜契约。
- 无法解释 verifier/test 为什么存在，或无法解释原创题如何完成。
- 专家经验只是通用 coding 流程，对题目难点没有实质帮助。
- 专家经验泄漏 verifier、测试实现、隐藏 workload、答案或预期输出。
- 任务能通过搜索直接找到 solution。

## 动态质量激励目标

需求文档“数据质量评价”第一条是交付硬门禁：首轮格式达标、内容相关、符合手册、无拒绝验收项，并通过最新版 checker。只要第一条通过，即属于可提交的合格数据。

第二条明确属于“内部检测，质量激励”。固定题目版本后，尽量用可复现的 agent workflow 运行两组来追求：

1. **任务价值。** no-skill seed 在声明预算内不能通过独立 verifier，或者只有在超过 100 轮后才通过。
2. **skill 有效性。** 满足下列之一：
   - no-skill 未通过，with-skill 通过；
   - no-skill 超过 100 轮才通过，with-skill 也通过，并且轮次和时长经独立 reviewer 判断显著降低。

两组应使用相同冻结题目、准确的 `seed` 模型版本、环境、资源上限和 verifier 版本。除冻结的 `expert_experience_skill` 外，不给 with-skill 组额外信息。报告模型标识、命令、开始/结束时间、退出码、轮次、时长、答案哈希、verifier 哈希与结果。为了声称第二条目标达成，no-skill 失败分支应至少运行 100 轮；不足 100 轮只能标记为 `inconclusive`。第二条未达成、证据不足或因成本未运行，不得推翻第一条的合格结论，也不得阻止打包和飞书提交。

本批次把“显著降低”操作化为：当两组都通过时，with-skill 相对 no-skill 的轮次或时长降低至少 30%，50% 是努力目标。降低率分别按 `(no_skill - with_skill) / no_skill` 计算。no-skill 未通过而 with-skill 通过是独立的目标达成分支，不强行给未完成轨迹计算百分比。

`quality-decision.json` 至少包含：

```json
{
  "candidate_id": "string",
  "decision": "pass",
  "acceptance_basis": "data_quality_item_1",
  "reviewer": "independent reviewer or harness id",
  "reviewed_at": "ISO-8601 timestamp",
  "artifacts": {
    "proposal_sha256": "64-character SHA-256 from validate-proposal.ps1",
    "delivery_sha256": "64-character SHA-256 from validate-proposal.ps1"
  },
  "gates": {
    "format": "pass",
    "content_relevance": "pass",
    "originality": "pass",
    "solvability": "pass",
    "verifier_quality": "pass",
    "anti_leakage": "pass",
    "baseline_value": "not_met",
    "skill_effect": "not_run"
  },
  "quality_incentive": {
    "status": "not_met",
    "notes": "No-skill passed within 100 turns; item 2 is not met but item 1 remains accepted."
  },
  "runs": {
    "no_skill": {"solved": false, "turns": 100, "duration_seconds": 0},
    "with_skill": {"solved": true, "turns": 0, "duration_seconds": 0}
  },
  "evidence": {
    "static_review": "path relative to this decision file or absolute path",
    "no_skill_run": "optional path when run",
    "with_skill_run": "optional path when run",
    "verifier_report": "optional path when run"
  }
}
```

硬门禁是 `format`、`content_relevance`、`originality`、`solvability`、`verifier_quality`、`anti_leakage` 全部为 `pass`。`baseline_value` 和 `skill_effect` 是目标状态，可为 `pass`、`not_met`、`inconclusive` 或 `not_run`，必须真实填写，但不参与提交拒绝。`quality_incentive.status` 可为 `met`、`not_met`、`inconclusive` 或 `not_run`。

若存在运行数据，`turns` 与 `duration_seconds` 必须填真实非负值。只有 baseline 未解决且至少记录 100 轮，或已解决且 `turns > 100`，才可声称任务价值目标达成；两组都解决时，轮次或时长降低至少 30% 才可声称 skill 效果目标达成。未达到这些条件时，写入实际状态即可，打包脚本不得因此拒绝第一条已合格的数据。`artifacts` 必须取自冻结版本的结构校验输出，用于阻止质检后替换题面或 sources。

这里的 no-skill/with-skill 结论是供应侧交付前预检，不能代替需求方的正式二阶段跑分与验收。

## 交付与目录

```text
D:\hc\obm\
|-- cache\
|   `-- runs\<run-id>\candidates\<candidate-id>\...
|-- result\
|   `-- <task-id>\
|       |-- README.md
|       |-- {bench_name}_{proposal_name}.zip
|       |-- final-qc.png
|       `-- SHA256SUMS
`-- skills\obm-question-production\...
```

压缩包内部：

```text
{bench_name}_{proposal_name}\
|-- proposal.json
`-- sources\
    `-- ...
```

`sources/` 必须有实际内容并支持离线验收。质检证据保留在 `cache`，不改变官方交付层级。真实人工工时、专家经历证明和签字状态若由交付方提供，记录在外部交付表，不加入 ZIP，也不伪造为运行证据。

`result\<task-id>\README.md` 是本地交付索引，写明题目名、benchmark、最终结论、ZIP/截图文件名、校验和和飞书记录 ID；它位于 ZIP 外。`sources\README.md` 是需求规定的 Source 用途说明，位于 ZIP 内，两者不能互相替代。

正式生产任务必须持续推进候选，直到至少一个候选完整通过并上传回读。该完成条件不授权无上限消费；凭据/基础设施阻断或用户设定的成本、时间、候选数硬上限触发时，任务保持未完成并报告剩余工作。

`quality-decision.json` 建议保存于对应 `cache\runs\<run-id>\candidates\<candidate-id>` 目录；打包脚本会强制其引用的三类证据文件位于指定 `CacheDir` 下。
