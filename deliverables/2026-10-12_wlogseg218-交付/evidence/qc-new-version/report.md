# Windows Harbor 完整质检报告

结论：**BLOCKED**

- 交付目录：`PASS`
- 四模型门禁：`PASS`
- 四模型原始 jobs：`PASS`
- Oracle/NOP：`PASS`
- 十项人工质量复核：`BLOCKED`

## 交付目录

- 警告：source.json is absent; this is allowed and does not block QC

## 模型门禁

- 通过

## 模型 jobs

- 通过

## 十项人工质量硬门禁

- **Golden/NOP 得分和逐 testcase 终态符合预期**：`BLOCKED`
  - 说明：Golden/NOP 得分和逐 testcase 终态符合预期
- **每项评分标准和每个 testcase 判分正确**：`BLOCKED`
  - 说明：每项评分标准和每个 testcase 判分正确
- **Testcase 严格对应题面并检查功能而非固定写法**：`BLOCKED`
  - 说明：Testcase 严格对应题面并检查功能而非固定写法
- **模型没有联网取答案、搜索 Golden 或绕过评分**：`BLOCKED`
  - 说明：模型没有联网取答案、搜索 Golden 或绕过评分
- **题目具备真实 Windows 反事实价值**：`BLOCKED`
  - 说明：题目具备真实 Windows 反事实价值
- **范围、版本、公式和全部执行资产身份已冻结**：`BLOCKED`
  - 说明：范围、版本、公式和全部执行资产身份已冻结
- **WIP 94 项已逐项登记并提供证据或 N/A 依据**：`BLOCKED`
  - 说明：WIP 94 项已逐项登记并提供证据或 N/A 依据
- **采购手册 D01-D20 已逐项完成动态审计**：`BLOCKED`
  - 说明：采购手册 D01-D20 已逐项完成动态审计
- **已从 required testcase 和冻结公式独立复算正式分数**：`BLOCKED`
  - 说明：已从 required testcase 和冻结公式独立复算正式分数
- **原始证据、历史版本、整改和干净复验已闭环**：`BLOCKED`
  - 说明：原始证据、历史版本、整改和干净复验已闭环
- 错误：未提供十项人工质量复核；自动检查通过也不能签发最终 PASS

## 原始证据

- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志
- `delivery-layout.json`：目录与 task_id/version/hash 绑定
- `model-gate.json`：四模型次数、分数和区分度
- `model-jobs.json`：14 个 Harbor jobs（8 个模型、3 个 Oracle、3 个 NOP）交叉校验
- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件
