# quality_review —— wfflab__winstall-210

> 主方向：**构建、安装与打包**（12 个主流方向中的第 9 个，题包内此前未覆盖）
> 被测包：`winstall` 2.0.0（纯 Python 标准库）
> 身份：`task_id = wfflab__winstall-210` / `task_version = 1.0` /
> `task_hash = 57c6c3638f3565bca8d2071ea24461624991f616c1b7f50c76099ab117ef160a`
> 最后更新：2026-10-01

## 一、选题与反事实判定

**场景**：Windows 上的应用安装器必须能"要么全成、要么回到原样"。
真实世界的安装失败几乎总是发生在文件层：目标文件正被别的进程打开、
目标位置已被一个同名目录占据、升级到一半失败。

**反事实判定（必须通过）**：

| 判据 | 结论 |
|---|---|
| 换 Linux 后主要实现是否基本不变？ | **会变**。Linux 上 `unlink`/`rename` 对已打开文件直接生效，"被占用"这条约束不存在，写入无需做原子替换 |
| 换 Linux 后错误根因是否基本不变？ | **会变**。本题根因是 `MoveFileEx(REPLACE_EXISTING)` 在目标被打开时返回 `WinError 5` |
| 换 Linux 后 Evaluator 是否基本不变？ | **会变**。制造"被占用"的唯一手段（保持一个打开句柄）在 Linux 上不产生可观测差异，测试必须整体改写 |

→ 三条全部不满足"基本不变"，**通过** Windows 价值判定。

**依赖的 Windows 机制**（已实测，见第四节）：
`MoveFileEx` 的 REPLACE_EXISTING 语义与文件共享模式、`%ProgramData%` / `%LOCALAPPDATA%`
双作用域安装根、以及 pending-replace 记录（对应 Windows 的
`PendingFileRenameOperations` 思路）。

## 二、已完成并通过的检查

| # | 检查 | 证据 |
|---|---|---|
| 1 | 五件套齐全（`task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/`） | `_index/validate-report.json` |
| 2 | 身份四处一致（task.toml 注释 / swelive_spec.json / platform_import.json / metadata/manifest.json） | `57c6c363…` |
| 3 | 伴随材料六项齐全 | `_index/validate-report.json` |
| 4 | **no-change 得 0** | 本机 L2：`status=VALID score=0.0 pytest_rc=1 (3.0s)`，7 条 F2P 全失败、7 条 P2P 全通过 |
| 5 | **Golden 得 1** | 本机 L2：`status=VALID score=1.0 pytest_rc=0 (3.0s)`，14/14 |
| 6 | 可见回归测试在 base 与 golden 上都通过 | base `11 passed`；golden `25 passed`（11 可见 + 14 隐藏） |
| 7 | 题面与 required 双向映射 | `extras/testcase_mapping.csv` R1–R14 |
| 8 | 二值判分、无权重、无部分分、无 LLM Judge | `tests/grade.py` 只按 required 全过 / 否则 0 |
| 9 | 无答案与隐藏测试泄漏 | Agent 可见面只有 `environment/workspace/` |

## 三、证据缺口（阻塞验收）

| # | 缺口 | 现状 |
|---|---|---|
| 1 | 镜像未构建，`image_digest` 为 `PENDING_BUILD` | 与其余各题相同，需 Windows 构建机 |
| 2 | 对照证据矩阵未生成（`extras/evidence/`） | 待 `build_evidence.py` 跑完 |
| 3 | 多模型验证未完成（Qwen 3 / Opus 3 / GLM 1 / Kimi 1） | 运行中 |
| 4 | 采购方复验与冻结 | 未开始 |

### 关于缺口的诚实说明

本机 Windows 11 上完成的 L2 校验是**等价实现**，不能替代镜像内复现。
镜像构建完成后必须在容器内重跑 no-change 3 次 + Golden 3 次。

## 四、真实模型运行结果

见 `extras/remediation_and_retest.md` 与 `extras/model_runs/`。

## 五、Hack 与答案泄漏审查（四层分级）

| 层级 | 检查项 | 结论 |
|---|---|---|
| 静态 | Agent 可见面是否含答案 | 否。`environment/workspace/` 只含被测包与可见测试 |
| 静态 | 工作区 git 历史是否含上游答案 | 否。镜像内只有一个 baseline commit |
| 静态 | 判分是否可被模型改动 | 否。`test.ps1` 先从 HEAD 还原 test_patch 触碰的文件，再应用补丁 |
| 静态 | 测试是否靠反编译/猜测可过 | 否。required 断言的是**文件系统终态与清单内容**，必须真的实现事务语义 |
| 动态 | 是否有"不实现也能过"的捷径 | 待模型运行结束后审查各模型补丁 |

## 六、题面与测试公平性复核

**每一条 required 都能在题面里找到出处**（见 `testcase_mapping.csv` 的
`requirement_source` 列）。特别地，本题最容易被认为"苛刻"的两点，题面都已明文写出：

1. **"可延迟"与"硬失败"要分开** —— 题面「目标 2 / 目标 3」分别列出两种失败的处理方式，
   验收标准 4–7 逐条对应。
2. **不得残留临时文件** —— 题面验收标准 7 明文写出。

**没有测试过约束**：隐藏测试不检查任何题面未声明的东西
（不检查内部函数名、不检查临时文件的命名、不检查 `_is_deferrable` 这类私有实现，
也不要求特定的错误消息）。

**等价实现的容忍度**：只要满足公开 API 的行为契约，内部怎么实现都可以
（`extras/evidence/negative_and_equivalent_controls/equivalent_01_alternate_impl`
给出一个刻意换掉全部 API 的等价实现，必须同样得 1.0）。
