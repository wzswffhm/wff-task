---
name: windows-harbor-qc
description: 对 Outside Harbor Windows 题包或 ZIP 做本地真实 Harbor 质检，检查 Demo 目录、Windows 环境、测试与二值评分，并运行 Oracle/NOP 生成可审计报告。
---

# Windows Harbor QC

用于质检 Windows 专项 Harbor 题包。输入应是一个题目目录或交付 ZIP；默认只在本地生成证据，不修改题包、不修改飞书、不上传外部系统。

先阅读 [references/checklist.md](references/checklist.md)，再运行唯一推荐入口：

```powershell
python scripts\run_qc.py `
  --input D:\path\delivery.zip `
  --out D:\path\qc-result
```

入口会安全解包、发现所有 `task.toml`、检查 Outside Harbor Demo 结构和身份一致性，然后在 Windows Docker 容器中真实执行 Harbor `oracle` 与 `nop`。每个 Agent 默认独立运行 3 次；需要严格稳定性复验时使用 `--attempts 6`。每轮固定使用：

```text
--n-attempts 1 --n-concurrent 1 --max-retries 0
```

判定门禁是硬条件：

- Oracle 每一轮必须是完整 `VALID/1`；
- NOP 每一轮必须是完整 `VALID/0`；
- NOP 的每一轮 P2P 必须全部 PASS，且至少一个核心 F2P FAIL；
- 缺 testcase、重复 testcase、SKIP、ERROR、NOT_RUN、解析错误、Harbor 异常或基础设施故障必须是 `INVALID/BLOCKED`，不能把 `reward=0` 当作有效模型 0 分；
- 测试必须验证真实 Windows 行为并允许等价实现，不能用源码关键词、Diff、文件存在、日志字符串或模型自报替代核心断言。

结果目录包含 `report.md`、`report.json`、`inventory.json`、`hashes.json`、`commands.json`、`preflight.json`、`runs.json`、`jobs/`、`staged/` 和每轮 Harbor CLI 原始日志。Oracle CLI 日志是 Oracle 成功的直接文字证据；需要截图时，应从对应 CLI 日志或 Harbor 控制台截取，不得用手工分数截图代替原始结果。

若要完成正式模型准入，再对本地模型运行证据执行 `python scripts\validate_model_gate.py --input model-evidence.json`。该校验器要求 Qwen 与 Opus 各 3 次 `VALID` 二值运行，并按“Opus 总分严格更高；或双方总分均为 0 且 Opus testcase PASS 总数严格更高”判定；GLM、Kimi 各至少 1 次有效运行。无效运行不能按 0 分计入。

退出码：`0` 为全部门禁通过，`1` 为题包或动态质量不通过，`2` 为本机依赖/Windows Docker/输入证据不足而无法完成真实质检。

必须使用真实 Windows 容器模式、可用的 Docker 和 Harbor CLI。不要通过减少 required 清单、改写测试、跳过 Oracle/NOP、复用旧 jobs 或修改输入题包来消除失败。若需要修复题包，应另行复制到新的版本目录，修复后用新的空结果目录重新运行。
