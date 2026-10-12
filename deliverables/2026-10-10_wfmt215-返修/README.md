# wfflab__wfmt-215 返修交付（v2.0.0 → v2.1.0）

## 0. 结构对齐参考包 `harbor-record-42`

按质检对同批次姊妹题（216）给出的结构意见，本题包一并重组为参考包的单根形态：

| 项目 | 重组前（第一版 v2.1.0） | 重组后 |
|---|---|---|
| zip 顶层 | `jobs` + `outside_harbor` + `outside_harbor-assets` + `outside_harbor-verifier` | **只有** `wfflab__wfmt-215-v2.1.0-delivery/` |
| 题包位置 | 五件套在 `outside_harbor-assets/<task>/` 下 | `instruction.md`/`task.toml`/`environment`/`solution`/`tests`/`jobs` **平铺在根** |
| `environment/adapter.toml` | 仅 `[prepare]` 等表格 | 顶部加**扁平入口键** `prepare`/`validate`/`run`/`restore`/`cleanup`/`workspace`（+`start`/`test`/`exec_agent`） |
| jobs trial 命名 | `wfflab__wfmt-215__qwen3.8-…` | **`task__XXXXXX` ×8**（模型）+ **`task0__XXXXXX` ×6**（控制） |
| 判分侧材料 | `outside_harbor-verifier/<task>/` | 单根内 `verifier/`（不进 Agent 可见面、不出现在 zip 顶层） |

工具：`build_215_dist.py`（重组 + 结构自检）、`pack_215_single_root.py`（单根打包 + 顶层校验）。
旧的四目录版 zip 留档于 `package/four-dir-layout/`。跑分证据未变（仍是 v2.1.0 的 14 轮）。

飞书任务：`甲方ID 66 / record reczz28KwEOO3xHy`（状态字段不变，仅替换 `作业压缩包` 附件）。

基准：飞书附件 `wfflab__wfmt-215-v2.0.0-delivery.zip`（下载解包为本目录 `build/`，不以本地陈旧副本为准）。

## 返修对照（五条返修原因 → 改动）

| # | 返修原因 | 改动 |
|---|---|---|
| 1 | 答案泄露：包内含 `solution/oracle.patch`、`solution/reference/wfmt/`、解法说明 | `solution/` 仅保留无答案入口（`README.md` + `solve.ps1` + `solve.bat`）；参考实现/补丁移出至判分侧 `outside_harbor-verifier/…/oracle/`；原 `solution/README.md` 的格式常量说明已删 |
| 2 | 隐藏测试未隔离：`tests/hidden/…`、Rubric、判分规则在任务目录 | 隐藏断言移至 `outside_harbor-verifier/…/tests/test_wfmt_semantics.py`；判据明细移至 `rubric.conditions.json`；Agent 可见清单 `environment/agent_visible_paths.json`；`run_tests.ps1` 从注入根解析，未注入即 exit 2；`validate_environment.ps1` 增加隔离断言 |
| 3 | 环境不可离线复现：联网装 Choco/Git/Python/pip，Git 未锁版本 | `Dockerfile` 全离线：vendored MinGit 2.56.0.2 + Python 3.12.9 embed + wheelhouse（`--no-index`），无 Choco/网络；`vendor/INVENTORY.json` 锁 sha256 |
| 4 | 镜像未锁不可变摘要：可变标签 `ltsc2022` | `FROM mcr…:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a`；task 镜像重建并锁定 digest |
| 5 | judge 权重违反 WIP VV-14：`programmatic_weight=1.0`（100% > 50%） | `judge.toml`：`programmatic_weight=0.5` / `llm_judge_weight=0.5`；`rubric.json` 拆为 programmatic(5 项, 合计 0.5) + llm_judge(4 项, 合计 0.5)；`aggregate_results.ps1` 只让 programmatic 项参与二值门 |

其余要求：题面（`instruction.md`）不含答案、代码无引导性注释；`task_version` 2.0.0 → **2.1.0**，`task_hash`/镜像 digest 已刷新。

## 包结构（三层）

```
outside_harbor/wfflab__wfmt-215.json            平台导入描述
outside_harbor-assets/wfflab__wfmt-215/         Agent 可见题包（instruction/task/source/env/tests 入口/solution 入口）
outside_harbor-verifier/wfflab__wfmt-215/       判分侧（隐藏断言 + oracle/reference + rubric.conditions + 证据）
jobs/                                           历史跑批证据
```

## 验证证据（本目录 `evidence/`）

- `docker-build.log` — 全离线镜像构建成功（vendored 安装，无网络步骤）
- `container-check/` — 直接容器验证：NOP=VALID/0，ORACLE=VALID/1，权重 0.5/0.5
- `logic-check/` — 隐藏套件移位后仍区分基线（8 FAIL）与参考实现（15/15 PASS）
- `runner-controls.log` — 本地 runner 端到端：no-change verdict=0/VALID，golden verdict=1/VALID

## 模型跑批（重跑）

按指示：**先重跑 Qwen；只有 Qwen 没有全部满分时再跑其他模型**。

Qwen 三轮 `[0, 0, 0]`（满分 0 < 3）→ 继续跑 OPUS×3 / KIMI×1 / GLM×1。

## 跑分结果（v2.1.0，14 轮全 VALID）

| 角色 | trial | verdict |
|---|---|---|
| oracle（golden） | `golden-01-26df` / `-01-a9d2` / `-01-5955` | **1 / 1 / 1** |
| nop（no-change） | `no-change-01-41d7` / `-01-948d` / `-01-2b38` | **0 / 0 / 0** |
| QWEN 3.8-max | `qwen3.8-max-0902-01-11f4` / `-02-776f` / `-03-43ba` | **0 / 0 / 0** |
| OPUS 5 | `opus-5-01-0c6d` / `-01-1a69` / `-01-a983` | **1 / 1 / 1** |
| KIMI K3 | `kimi-k3-01-6118` | **0** |
| GLM 5.3 | `glm-5.3-01-5457` | **0** |

**门禁判定全部通过**：

| 门禁项 | 要求 | 实测 |
|---|---|---|
| oracle 控制轮 | 3 轮 = 1 | 1/1/1 ✅ |
| nop 控制轮 | 3 轮 = 0 | 0/0/0 ✅ |
| 有效轮数 | QWEN≥3、OPUS≥3、GLM≥1、KIMI≥1 | 3/3/1/1 ✅ |
| **区分度** | **OPUS 总分 > QWEN 总分** | **3 > 0** ✅ |
| run_validity | 全部 VALID | 14/14 ✅ |
| 跑分时身份绑定 | 每轮带 `task_identity.json` | 14/14 ✅ |

跑分时段：2026-10-10 22:17 → 2026-10-11 13:13（本地 runner，Windows 容器）。

## 归档与校验

`jobs/` 按 `harbor-record-42` 参考格式重建（`config.json` / `result.json` / `lock.json` / `job.log` + 14 个 trial 目录），
轮次由 `assemble_215_jobs_archive.py` 从 `runs/` **自动发现**（只收 `task_version=2.1.0` 且非 INVALID 的轮，
按 3/3/3/1/1 配额取最早 N 个，排除项写进 `lock.json` 的 `excluded_rounds`）。

| 校验 | 结果 |
|---|---|
| `verify_215_v21_archive.py` | **514 项检查，0 问题**（逐字节同源、reward 自洽、身份绑定、source_mapping 全覆盖、门禁断言） |
| 静态隔离 `_audit.py` / 逻辑 `_logic_check.py` / 容器 `_container_check.py` | 见 `evidence/` |

身份三口径：

| 口径 | 值 |
|---|---|
| 平台导入 | 见 `build/outside_harbor-assets/wfflab__wfmt-215/platform_import.json` |
| 整树 | `f6b79bde461386460500f36f6a4fa73c461901a54b118710610e01f835bafa5d` |
| runner 跑分 | `0717bd259497adec79197574d6891c35465b294b6fa833f5ab7561ab9336860e`（14 轮 `task_identity.json` 一致） |

## 交付与上传

| 文件 | 大小 | sha256 |
|---|---|---|
| `package/wfflab__wfmt-215-v2.1.0-delivery.zip`（单根结构） | 52.8 MiB（396 entries） | `77479dee9a3092f8f2f4bdf26e1454adee5dc173aa704d1d302977fd633f8b7f` |

已上传飞书记录 `reczz28KwEOO3xHy`（标注员 wff）：作业压缩包 `wfflab__wfmt-215-v2.1.0-delivery.zip`（55,325,959 B）、
`score_summary.png`（69,589 B）、`oracle_nop_controls.png`（108,042 B），「文本」字段同步为 v2.1.0；
状态字段未改动（仍为「待返修」，流转由标注员/流程决定）。留档见 `evidence/upload-143.json`。

原始 v2.0.0 包留在 `downloads/`（sha256 `ad1478b3d03f24b6bb52aa62679b16494020974d185ed5772d9b6c922a24c492`）作"整改前"对照。

## 与 v2.0.0 原包的结构差异

原包 `jobs/` 是 runner 侧旧索引形态（`jobs/_index/jobs_index.csv` + `qualification_summary.json`，
指向 20261007–20261008 的旧轮次，csv 内为本机绝对路径）；v2.1.0 归档按 42 参考格式重建 `jobs/` 根，
旧轮次与旧索引不再沿用。

## 基础设施故障记录

首次控制轮出现 2 个 INVALID（`221515-no-change`、`221521-golden`），原因是 Windows 容器 bind mount 在
多会话并发负载下的间歇性失效（verifier 未注入 → `verifier produced no result.json`）；已由
`run_rounds.ps1` 的自动重跑补齐，这两个失效轮已从 `runs/` 清除。

