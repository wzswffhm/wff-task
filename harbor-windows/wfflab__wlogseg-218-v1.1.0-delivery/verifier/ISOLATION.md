# 隔离边界与适配口径（wfflab__wlogseg-218，task version 1.1.0）

对应质检条目：`ZQ004-06 / ZQ005-06｜风险｜模型可读取公开仓库测试，缺手册隔离条款的适配说明`。
口径版本：**isolation-adaptation-v2（2026-10-13）**。

> **免责声明**：本说明是对 `wfflab__wlogseg-218` 的隔离口径澄清与分层声明。
> 原始轨迹与原始分数保持原样；本说明只新增口径，不改写历史。

## 0. 判分套件是怎么进容器的（平台机制，先写清楚）

这道题的隐藏断言必须由平台在判分阶段投放。实测 Harbor 的 Windows 通道有两条，
本题只依赖第一条：

| 通道 | 平台行为 | 本题是否使用 |
| --- | --- | --- |
| `C:\tests` | Harbor 在跑 `tests/test.ps1` **之前**，把**包根 `tests/` 目录**整体复制到容器内 `C:\tests`（`harbor/models/trial/paths.py` 的 `EnvironmentPaths.tests_dir = C:/tests`） | **使用**：`tests/test_wlogseg_semantics.py` 经此进入容器 |
| `C:\verifier` | 判分侧独立注入点，由外部 harness 按 `verifier/` 内容投放；本题容器内不存在该目录 | 作为**优先候选**声明，命中即用（本地复现与具备注入能力的平台） |

因此**套件必须在包根 `tests/` 里放一份**——这是平台的投放契约，不是可选项。
v1.0.0 的缺陷不在于"放了"，而在于**解析顺序里没有显式声明 `C:\tests` 为只读通道**，
却把候选自己的工作区放在可解析路径上：候选改写 `environment/workspace/tests/` 下的
同名文件，就可能让判分取材落到自己手里。

## 1. 三层材料清单（公开开发测试 / 隐藏验收 / 参考解）

| 层 | 包内路径 | 容器内位置 | 作答期可见性 | 用途 | 作答期权限 |
| --- | --- | --- | --- | --- | --- |
| 公开开发测试 | `environment/workspace/tests/test_wlogseg_basic.py` | `C:\testbed\tests` | **可见** | 冒烟：证明"自己写的自己能读回来"；题面 G 节要求它继续通过 | 只读 |
| 公开契约文档 | `environment/workspace/docs/FORMAT.md` | `C:\testbed\docs` | **可见** | 早期草稿，题面已声明不可作为依据 | 只读 |
| 权威样本 | `environment/workspace/assets/` | `C:\testbed\assets` | **可见** | 题面明确的唯一权威依据 | 只读 |
| **隐藏验收断言** | `tests/test_wlogseg_semantics.py`（平台投放副本）+ `verifier/tests/test_wlogseg_semantics.py`（判分侧正本） | `C:\tests\test_wlogseg_semantics.py` | **只读可见**（见 §1.2 口径） | 唯一的判分断言来源 | 只读；不参与 `mutable_paths` |
| 判据与归因 | `verifier/rubric.conditions.json` | 不投放 | **不可见** | 每条 rubric 的判据、失败归因 | 无 |
| 参考解实现 | `verifier/oracle/reference/wlogseg/` | `C:\solution\reference\wlogseg\`（仅 Golden 轮） | **不可见** | Golden 控制组 | 仅 Golden 轮 |
| 参考解入口 | `verifier/oracle/solve.ps1`、`solve.bat` | `C:\solution\`（仅 Golden 轮） | **不可见** | 安装参考实现 | 仅 Golden 轮 |
| 参考解说明留档 | `verifier/oracle/README-original.md`、`README.md` | 不投放 | **不注入** | 审计留档 | 无 |
| 分类与隔离口径 | `verifier/WINDOWS_VALUE.md`、本文件、`verifier/negative_access_probe.ps1` | 不投放 | **不注入** | 采购分类与隔离审计 | 无 |

机器可读的可见面清单：`environment/agent_visible_paths.json`
（`visible_in_agent_container` / `not_present_in_agent_container` / `verifier_side_material`）。

### 1.2 为什么把套件放进 `tests/` 仍然满足隔离要求

甲方要防的是**未授权读取隐藏测试、参考修复或修改评分材料**，而不是"目录名里出现
tests"。本题的实际边界是：

1. **判分取材不可被候选篡改**：`run_tests.ps1` 的解析顺序是
   `-VerifierRoot` → 环境变量 → `C:\verifier\wfflab__wlogseg-218` → `C:\verifier`
   → `C:\tests` → 包内平级 `outside_harbor-verifier\…`（仅本地复现，不进容器）。
   **workspace 不在其中**；`C:\tests` 是平台在判分阶段投放的只读副本，候选改不到。
   候选对 `environment/workspace/tests/` 的任何改动都不会被判分采纳。
2. **只读性有双重声明**：`environment/adapter.toml` 的 `agent_read_only_paths` 与
   `environment/agent_visible_paths.json` 都把 `tests/` 标为 read-only；
   `task.toml` 的 `policy.mutable_paths` 只有 `environment/workspace/wlogseg`。
3. **参考解始终不可见**：`solution/` 只在 Golden 轮注入，候选容器内不存在；
   `verifier/` 从不投放到候选容器。
4. **负访问有实测证据**：`verifier/negative_access_probe.ps1` 以 agent 同身份只读运行，
   逐项检查并输出 JSON（见 §3）。

### 1.3 与 v1.0.0 的差异

| 项 | v1.0.0 | v1.1.0 |
| --- | --- | --- |
| 包内 `tests/` 套件副本 | 有（唯一副本） | 有（**平台投放副本**，与 `verifier/tests/` 正本 sha256 相同） |
| 解析顺序是否显式声明 `C:\tests` | **否**（按路径拼接隐式命中） | **是**，作为只读通道显式声明 |
| 解析顺序是否可能落到候选工作区 | 是（`Join-Path $TaskRoot 'tests'`） | **否**（workspace 完全不在列表内） |
| 判分侧正本是否独立存在 | 否 | **是**（`verifier/tests/` 已封入 `SEALED_MANIFEST.json`） |
| 负访问证据 | 无 | **有**（探针 + 归档 JSON） |

## 2. 作答期权限口径

- agent 可见根只有 `C:\testbed`（workspace）；**唯一的可写面是 `C:\testbed\wlogseg`**。
- `assets/`、`docs/`、`tests/` 在 agent 容器内以只读方式呈现
  （`agent_visible_paths.json` 与 `environment/adapter.toml` 的
  `agent_read_only_paths` 双重声明）。
- `C:\verifier`、`C:\solution` 与判分侧材料都不在候选容器内；判分入口两处都解析不到
  套件时以退出码 2 报 `INVALID`，不会退化成 0 分。

### 公开开发测试为什么保留可见

题面 G 节明确要求 `environment/workspace/tests/test_wlogseg_basic.py` 继续通过，
它是候选唯一的自查手段。该文件只断言"自产容器自读往返"，不含样本期望值、不含
隐藏断言、不含参考实现，因此**模型读取它是设计内行为，不构成答案泄漏，也不代表
隔离失效**。

### 采购方适配口径（版本化）

本包按 `isolation-adaptation-v2` 交付。若采购方的隔离手册要求更严格的形态，需按
下列变更点对齐（变更是版本化的，不回写旧轮次）：

| 采购方要求 | 需要的变更 | 影响 |
| --- | --- | --- |
| 判分套件不得出现在候选容器任何路径 | 需要平台支持"判分阶段才投放"的独立通道（如把套件改为经 `C:\verifier` 投放并要求平台具备该注入能力）；否则需放弃 Harbor 的 `C:\tests` 通道 | 需平台侧确认；本包当前的 `C:\tests` 副本是 Harbor 明文契约 |
| 公开开发测试一律不可见 | 把 `tests/test_wlogseg_basic.py` 移出 workspace，改由判分侧在 G 节前注入 | 需升版本并重跑控制组与模型；旧轮不追溯 |
| 权威样本也需隐藏 | 把 `assets/` 移出 workspace 并改成判分期注入 | 同上；且题面 A 节的自查方式会变 |
| 参考解说明也必须可审计可见 | 仅移动 `verifier/oracle/README-original.md` 的位置，不改判分 | 无判分影响 |

## 3. 负访问验证（可复现）

以**与 agent 相同身份**运行只读探针：

```powershell
# 在候选包根目录执行（等价于 agent 容器内的同一检查）
powershell -NoProfile -ExecutionPolicy Bypass -File verifier\negative_access_probe.ps1 -TaskRoot <包根>
# 判分环境的就绪探针（同一套隔离断言）
powershell -NoProfile -ExecutionPolicy Bypass -File environment\validate_environment.ps1 -TaskRoot <包根>
```

探针逐项检查并输出 JSON 证据：

1. agent 可见树内不得出现 `oracle` / `golden` / `reference` / `hidden` / `rubric` /
   `solution` / `reward` 命名的文件；
2. workspace 内不得出现隐藏套件的函数名或样本期望值片段；
3. `C:\solution`、`C:\verifier` 解析后不得落在 agent workspace 之内；
4. 隐藏套件与参考解必须在判分侧存在（`verifier/tests/`、`verifier/oracle/reference/`），
   即隐藏材料确实被移出了 agent 可见面，而不是"根本不存在"；
5. 包内 `tests/` 的平台投放副本必须存在，且与 `verifier/tests/` 正本 **sha256 相同**
   （防止出现两份不同步的套件）；
6. 解析顺序不得包含 workspace（候选不可能提供判分断言）；
7. 可写面只有候选包（`environment/workspace/wlogseg`）。

本机运行输出归档在质检运行记录目录（按落盘纪律不入包）。

## 4. 结论

判分取材来自**平台投放的只读副本**与**判分侧正本**，候选工作区完全不在解析路径上；
参考解与判据在候选容器内不存在；每一项都由探针实测并留档。本说明与探针输出共同
构成 `ZQ004-06` / `ZQ005-06` 的闭环证据。
