---
name: windows-harbor-qc
description: 对 Outside Harbor Windows 题包或 ZIP 做本地真实 Harbor 质检，检查 Demo 目录、Windows 环境、测试与二值评分，并运行 Oracle/NOP 生成可审计报告。
---

# Windows Harbor QC

用于质检 Windows 专项 Harbor 题包。输入应是一个题目目录或交付 ZIP；默认只在本地生成证据，不修改题包、不修改飞书、不上传外部系统。

> ⚠️ **旧版动态质检入口已于 2026-10-12 移除**
>
> 本参考包原有的唯一入口 `scripts/run_qc.py`，连同它的 PowerShell 包装 `scripts/run_qc.ps1`
> 与单元测试 `tests/test_run_qc.py`，已按用户指示删除（判定为旧版）。因此本目录**不再提供**
> 一条命令跑完「静态检查 + Windows 容器动态 Oracle/NOP」的入口。
>
> 动态 Oracle/NOP 门禁现由 `harbor-windows/skills/harbor-windows/` 下的校验脚本承担
> （`validate_package.py`、`run_model_validation.py`、`run_trials.py` 等）。
> 本文件与 [references/checklist.md](references/checklist.md) 中关于 `run_qc.py` 的**判定口径**
> 仍作为门禁标准的历史依据保留，用于复核已归档在 `harbor-windows/_qc_runs/` 的既有证据。

保留的可用件：

| 文件 | 用途 |
|---|---|
| `scripts/validate_model_gate.py` | 模型区分度准入校验（见下文） |
| `scripts/run_trials.py` | 批量跑模型 trial |
| `scripts/windows_qc_env.py` | Windows 容器环境扩展（`--environment windows_qc_env:WindowsQCEnvironment`） |
| `scripts/qc_utils.py` | 上述脚本共用的读写/hash 工具 |
| `references/checklist.md` | 静态+动态门禁清单（判定标准） |

## 门禁判定标准（历史口径，继续有效）

每个 Agent 默认独立运行 3 次；需要严格稳定性复验时用 `--attempts 6`。每轮固定使用：

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

## 模型区分度准入

若要完成正式模型准入，对本地模型运行证据执行：

```powershell
python scripts\validate_model_gate.py --input model-evidence.json
```

该校验器要求 Qwen 与 Opus 各 3 次 `VALID` 二值运行，并按“Opus 总分严格更高；或双方总分均为 0 且 Opus testcase PASS 总数严格更高”判定；GLM、Kimi 各至少 1 次有效运行。无效运行不能按 0 分计入。

退出码：`0` 为全部门禁通过，`1` 为题包或动态质量不通过，`2` 为本机依赖/Windows Docker/输入证据不足而无法完成真实质检。

必须使用真实 Windows 容器模式、可用的 Docker 和 Harbor CLI。不要通过减少 required 清单、改写测试、跳过 Oracle/NOP、复用旧 jobs 或修改输入题包来消除失败。若需要修复题包，应另行复制到新的版本目录，修复后用新的空结果目录重新运行。
