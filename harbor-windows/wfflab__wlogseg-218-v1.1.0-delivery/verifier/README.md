# 判分侧材料（wfflab__wlogseg-218，task version 1.1.0）

本目录**不是 Agent 题包的一部分**，也不会被 `environment/Dockerfile` 打进
候选镜像。评测侧在判分阶段把它注入到容器内独立路径：

| 本目录 | 容器内注入点 | 用途 |
| --- | --- | --- |
| `tests/test_wlogseg_semantics.py` | `C:\verifier\wfflab__wlogseg-218\tests\` | 隐藏行为断言（pytest） |
| `rubric.conditions.json` | `C:\verifier\wfflab__wlogseg-218\` | 每条 rubric 的判据与失败归因 |
| `oracle/reference/wlogseg/` | `C:\solution\reference\wlogseg\` | Golden / Oracle 参考实现 |
| `oracle/solve.ps1`、`oracle/solve.bat` | `C:\solution\` | Oracle 安装入口 |
| `oracle/README-original.md`、`README.md` | 不注入 | 参考实现与 `docs/FORMAT.md` 草稿的差异说明、错误分类判据（审计用） |
| `WINDOWS_VALUE.md` | 不注入 | Windows 价值逐条映射与采购分类（质检 ZQ00x-03） |
| `ISOLATION.md` | 不注入 | 公开开发测试 / 隐藏验收 / 参考解的分层与适配口径（质检 ZQ00x-06） |
| `negative_access_probe.ps1` | 不注入 | 负访问只读探针，产出可归档的隔离证据 |
| `SEALED_MANIFEST.json` | 不注入 | 本目录全部文件的 sha256 / size 清单 |

Agent 可见面只有 `environment/workspace/`（容器内为 `C:\testbed`）：`tests/` 的隐藏
断言与 `solution/` 的参考解都只存在于判分侧，Agent 容器内不存在。

> **v1.0.0 → v1.1.0 的隔离整改**：v1.0.0 的解析顺序按路径拼接命中包内
> `tests/`，且把候选工作区放在可解析路径上；v1.1.0 把 `C:\tests` 作为**平台投放的
> 只读通道显式声明**，解析顺序里彻底移除候选工作区与任务根，并补齐判分侧正本的
> sha256 对账与负访问探针。

## 注入约定

判分脚本按下列顺序解析隐藏断言根目录，命中即用：

1. `run_tests.ps1 -VerifierRoot <dir>`；
2. 环境变量 `WLOGSEG_VERIFIER_ROOT`；
3. `C:\verifier\wfflab__wlogseg-218`；
4. `C:\verifier`；
5. `C:\tests`（Harbor 在跑 `tests/test.ps1` 之前把包根 `tests/` 复制到此，
   这是平台唯一的套件投放通道）；
6. 包内平级目录 `<包根>\outside_harbor-verifier\wfflab__wlogseg-218`（本地复现用，
   不进容器）。

列表中**不含**候选工作区（`C:\testbed`、`environment\workspace`）与任务根
`<任务根>\tests`：候选永远不能提供判分断言。`tests/` 在候选容器内是只读的
（`agent_visible_paths.json` 与 `adapter.toml` 双重声明）。

参考实现按 `solution/solve.ps1` 的解析顺序注入（`C:\solution\reference\wlogseg`
优先）。两处都解析不到时判分入口以退出码 2 报 INVALID，不会退化成 0 分。

## 版本与评分口径

- `task_version = 1.1.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、
  `llm_judge_weight = 0.0`（1.0.0 曾声明 0.5 的评审权重但从未采集分，已废止，
  见包根 `REFIT-2026-10-13.md`）。
- required testcase 共 **26** 条：F2P 18 条 / P2P 8 条；全过为 1，否则为 0，
  required 缺失或未终态一律 INVALID。
