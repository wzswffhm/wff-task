# 隔离边界与适配口径（wfflab__wchunk-216）

对应质检条目：`ZQ004-06｜风险｜模型可读取公开仓库测试，缺手册隔离条款的适配说明`。
口径版本：**isolation-adaptation-v1（2026-10-12）**。

> **免责声明**：本说明是对已交付产物 `wfflab__wchunk-216-v1.2.0-delivery`
> 的隔离口径澄清，**不代表修改或重评了原始产物**；原始轨迹与原始分数保持原样。

## 1. 三层材料清单（公开开发测试 / 隐藏验收 / 参考解）

| 层 | 包内路径 | 作答期可见性 | 用途 | 作答期权限 |
| --- | --- | --- | --- | --- |
| 公开开发测试 | `environment/workspace/tests/test_wchunk_basic.py` | **可见**（容器内 `C:\testbed\tests`） | 冒烟：证明"自己写的自己能读回来"；题面 F 节要求它继续通过 | 只读 |
| 隐藏验收断言 | `verifier/tests/test_wchunk_semantics.py` | **不可见**（判分期注入 `C:\verifier\wfflab__wchunk-216\tests\`） | 唯一的判分断言来源 | 不注入 agent 容器 |
| 判据与归因 | `verifier/rubric.conditions.json` | **不可见**（同上注入点） | 每条 rubric 的判据、失败归因 | 不注入 agent 容器 |
| 参考解实现 | `verifier/oracle/reference/wchunk/` | **不可见**（Golden 时注入 `C:\solution\reference\wchunk\`） | Golden 控制组 | 仅 Golden 轮 |
| 参考解入口 | `verifier/oracle/solve.ps1`、`solve.bat` | **不可见**（Golden 时注入 `C:\solution\`） | 安装参考实现 | 仅 Golden 轮 |
| 参考解说明留档 | `verifier/oracle/README-original.md` | **不注入** | 审计留档 | 无 |
| 历史判分产物 | `verifier/evidence/verifier-run/` | **不注入** | 上一轮 Oracle 运行留档 | 无 |
| 分类与隔离口径 | `verifier/WINDOWS_VALUE.md`、本文件、`verifier/negative_access_probe.ps1` | **不注入** | 采购分类与隔离审计 | 无 |

机器可读的可见面清单：`environment/agent_visible_paths.json`（`visible_in_agent_container`
与 `not_present_in_agent_container` 两份列表）。

## 2. 作答期权限口径

- agent 可见根只有 `C:\testbed`（workspace）；**唯一的可写面是 `C:\testbed\wchunk`**。
- `assets/`、`docs/`、`tests/` 在 agent 容器内以只读方式呈现（`agent_visible_paths.json`
  与 `environment/adapter.toml` 的 `agent_read_only_paths` 双重声明）。
- 隐藏验收断言与参考解**不在包内、不在镜像内、不在 agent 容器内**；判分侧按
  `verifier/README.md` 的解析顺序注入，两处都解析不到时判分入口以退出码 2 报
  `INVALID`，不会退化成 0 分。

### 公开开发测试为什么保留可见

题面 F 节明确要求 `tests/test_wchunk_basic.py` 继续通过，它是候选唯一的自查手段。
该文件只断言"自产容器自读往返"，不含格式真值、不含样本期望值、不含隐藏断言，
因此**模型读取它是设计内行为，不构成答案泄漏，也不代表隔离失效**。

### 采购方适配口径（版本化）

本包按 `isolation-adaptation-v1` 交付。若采购方的隔离手册要求更严格的形态，需按
下列变更点对齐（变更是版本化的，不回写旧轮次）：

| 采购方要求 | 需要的变更 | 影响 |
| --- | --- | --- |
| 公开开发测试一律不可见 | 把 `tests/test_wchunk_basic.py` 移出 workspace，改由判分侧在 F 节前注入 | 需升版本并重跑控制组与模型；旧轮不追溯 |
| 公开测试只读挂载改为完全不存在 | 移除 `agent_visible_paths.json` 中 `C:\testbed\tests` 条目并同步 adapter/Dockerfile | 同上 |
| 参考解说明也必须可审计可见 | 仅移动 `verifier/oracle/README-original.md` 的位置，不改判分 | 无判分影响 |

## 3. 负访问验证（可复现）

以**与 agent 相同身份**运行只读探针，检查隐藏材料在 agent 可见树内不可达：

```powershell
# 在候选包根目录执行（等价于 agent 容器内的同一检查）
powershell -NoProfile -ExecutionPolicy Bypass -File verifier\negative_access_probe.ps1 -TaskRoot <包根>
# 判分环境的就绪探针（同一套隔离断言）
powershell -NoProfile -ExecutionPolicy Bypass -File environment\validate_environment.ps1 -TaskRoot <包根>
```

探针逐项检查并输出 JSON 证据：

1. agent 可见树内不得出现 `oracle` / `golden` / `reference` / `hidden` / `rubric` /
   `solution` / `reward` 命名的文件；
2. `C:\solution`、`C:\verifier` 解析后不得落在 agent workspace 之内；
3. workspace 内不得出现隐藏套件的函数名或样本期望值片段；
4. 隐藏套件与参考解必须存在于**包内判分侧**（`verifier/`），即隐藏材料确实被
   移出了 agent 可见面，而不是"根本不存在"。

本机运行输出归档：`_qc_runs/refit-215-216/negative-access-216.json`（质检运行记录
目录，按落盘纪律不入包）。

## 4. 结论

隔离边界与公开测试的可见性都是**显式声明并被实测**的：公开层可见且有独立用途，
隐藏层不可见且不可达，参考解只在 Golden 轮注入。本说明与探针输出共同构成
`ZQ004-06` 的闭环证据。
