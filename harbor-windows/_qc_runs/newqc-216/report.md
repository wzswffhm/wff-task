# Windows Harbor 完整质检报告

结论：**FAIL**

- 交付目录：`FAIL`
- 四模型门禁：`FAIL`
- 四模型原始 jobs：`FAIL`
- Oracle/NOP：`FAIL`
- 十四项人工质量复核：`BLOCKED`

## 交付目录

- 错误：environment/Dockerfile:21 运行层使用禁止的 Nano Server/Server Core 镜像：mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a

## 模型门禁

- 错误：glm requires exactly 1 runs, got 0
- 错误：kimi requires exactly 1 runs, got 0

## 模型 jobs

- 错误：jobs/ must contain exactly 14 Harbor job directories, got 12
- 错误：jobs/ contains 0 glm model jobs; exactly 1 required
- 错误：jobs/ contains 0 kimi model jobs; exactly 1 required

## 十四项人工质量硬门禁

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
- **成品镜像远端可获取、甲方有权限、目标环境可启动并执行题目**：`BLOCKED`
  - 说明：按 references/image-delivery-gate.md 核验原始日志；本地成功不替代甲方交付
  - configured_image：""
  - resolved_image_digest：""
  - target_profile：{"windows_build": "", "architecture": "", "isolation": "", "can_build_images": null}
  - remote_pull：`BLOCKED`；实际成品镜像已显式从远端拉取，保留退出码和 digest
  - recipient_access：`BLOCKED`；甲方可拉取的公开访问或私有仓库权限依据
  - target_compatibility：`BLOCKED`；目标 Windows build、架构和实际隔离方式兼容性验证
  - clean_start：`BLOCKED`；同一镜像的新容器启动并确认就绪
  - task_execution：`BLOCKED`；同一镜像的标准 Harbor Oracle/NOP 和逐 testcase 证据
- **Windows 镜像不早于 2019，优先 2025，禁止 Nano Server/Server Core 和额外裁剪**：`BLOCKED`
  - 说明：2019 及以上，优先 2025；Nano Server 和 Server Core 均禁止
  - configured_image：""
  - family：""
  - runtime_bases：[]
- **实际使用的工具通过 Dockerfile 配置，并在成品容器内完成版本和功能验证**：`BLOCKED`
  - 说明：逐项登记任务、环境、Solution 和 Tests 实际需要的工具，并核验 Dockerfile 和容器内功能
  - tools：[]
- **实际使用嵌套虚拟化，外层 VM/扩展暴露/内层运行和当前 jobs 证据完整**：`BLOCKED`
  - 说明：必须实际使用嵌套虚拟化；Hyper-V 参数或 CPU 支持不能代替拓扑与内层运行证据
  - configured_image：""
  - task_id：""
  - task_version：""
  - task_hash：""
  - outer_guest_id：""
  - outer_hypervisor：""
  - inner_hypervisor：""
  - checks：{"outer_guest": {"status": "BLOCKED", "evidence": [], "notes": "外层 hypervisor 与 L1 Windows VM 标识/拓扑的原始证据"}, "capabilities_exposed": {"status": "BLOCKED", "evidence": [], "notes": "外层暴露虚拟化扩展且内层 hypervisor 实际启用"}, "inner_runtime": {"status": "BLOCKED", "evidence": [], "notes": "L1 内实际启动 L2 Windows VM/隔离容器的命令、日志和终态"}, "job_binding": {"status": "BLOCKED", "evidence": [], "notes": "当前 Task/镜像和实际模型、Oracle/NOP jobs 均绑定嵌套执行层"}}
- 错误：未提供十四项人工质量复核；自动检查通过也不能签发最终 PASS

## 原始证据

- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志
- `delivery-layout.json`：目录与 task_id/version/hash 绑定
- `model-gate.json`：四模型次数、分数和区分度
- `model-jobs.json`：14 个 Harbor jobs（8 个模型、3 个 Oracle、3 个 NOP）交叉校验
- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件
