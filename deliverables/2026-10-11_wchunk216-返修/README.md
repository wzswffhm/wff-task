# wfflab__wchunk-216 返修包（v1.2.0）

## 0. 第二轮返修：包结构对齐参考包 `harbor-record-42`

118 的第二轮质检意见（结构类，4 条）与整改：

| # | 质检意见 | 整改 |
|---|---|---|
| 1 | 压缩包不是标准单根目录结构（顶层有 `jobs`/`outside_harbor`/`outside_harbor-assets`/`outside_harbor-verifier`） | zip 顶层**只有** `wfflab__wchunk-216-v1.2.0-delivery/` |
| 2 | Task 根目录缺少必需项 `jobs/` | `instruction.md`/`task.toml`/`environment/`/`solution/`/`tests/`/`jobs/` 全部**平铺在单根下** |
| 3 | `environment/adapter.toml` 入口缺失或无法解析（`prepare`/`validate`/`run`/`restore`/`cleanup`/`workspace`） | adapter.toml 顶部加**扁平入口键**（上述 6 个 + `start`/`test`/`exec_agent`），原 `[table]` 段保留供本地 runner 使用 |
| 4 | `jobs/` 未形成可识别的 14 个标准 Harbor job | trial 改名为参考包形态：**`task__XXXXXX` ×8**（模型轮）+ **`task0__XXXXXX` ×6**（控制轮），索引里的 `trial_name`/路径/`original_locks` 同步更新 |

重组脚本 `_qc_runs/tools/build_216_dist.py`，打包脚本 `_qc_runs/tools/pack_216_single_root.py`
（已内置自检：顶层必须单一同名目录、根目录六项齐全、adapter 六个入口可解析、14 trial 命名正确）。

判分侧材料（隐藏断言 + 参考解）放在单根内的 `verifier/`，不进 Agent 可见面，也不出现在 zip 顶层。

本目录按飞书 **215 号记录**（`reczz28KwEOO3xHy`）的返修意见对 216 做同构整改，并在整改后的题包上重跑全部 14 轮，使本题的证据形态、判分隔离方式与权重拆分与 215 一致。

## 1. 215 的 5 条返修意见 → 216 的整改

| # | 215 返修意见 | 216 v1.2.0 的处理 | 证据 |
|---|---|---|---|
| 1 | 交付包含完整参考实现与解法说明 | `solution/reference/wchunk/` 与解法说明移出 Agent 可见包，改由判分侧注入；题包内只留 `solve.ps1` / `solve.bat` 入口 | `outside_harbor-verifier/wfflab__wchunk-216/oracle/` |
| 2 | 隐藏测试未隔离（只声明只读，未证明模型读不到） | `tests/hidden/test_wchunk_semantics.py` 移出题包，判分时注入 `C:\verifier\wfflab__wchunk-216`；新增 `environment/agent_visible_paths.json`；就绪探针把"工作区出现 oracle/reference/hidden/rubric 类文件"判为失败 | `environment/validate_environment.ps1`、`_audit.py` 输出 |
| 3 | 构建联网、Git 未锁版本 | Dockerfile 改为**全离线**：`vendor/MinGit-2.56.0.2-64-bit.zip`、`vendor/python-3.12.9-embed-amd64.zip`、`vendor/wheels/`（`--no-index` 安装 pytest/pytest-json-report），不再用 Chocolatey / python.org / get-pip | `environment/Dockerfile`、`environment/vendor/INVENTORY.json` |
| 4 | 基础镜像未锁摘要 | `FROM mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca…`（Dockerfile / task.toml / adapter.toml 三处一致） | 同上 |
| 5 | `programmatic_weight=1.0` 超 50% 上限 | 评分拆为 programmatic **0.5** / llm_judge **0.5**：6 条程序化条目（0.15/0.06/0.10/0.09/0.05/0.05）+ 4 条 LLM 判分条目（0.15/0.15/0.10/0.10），判据明细放判分侧 | `tests/judge.toml`、`outside_harbor-verifier/…/rubric.conditions.json` |

## 2. 目录结构

```
build/
  outside_harbor/wfflab__wchunk-216.json        平台导入描述符
  outside_harbor-assets/wfflab__wchunk-216/     Agent 可见题包（不含答案、不含隐藏断言）
  outside_harbor-verifier/wfflab__wchunk-216/   判分侧材料（注入 C:\verifier\<task>）
  jobs/                                         14 轮原始跑分证据（42 归档格式）
package/wfflab__wchunk-216-v1.2.0-delivery.zip  交付包（52.7 MiB）
evidence/                                       logic-check / container-check / model-runs 日志
```

## 3. 校验结果

| 校验 | 脚本 | 结果 |
|---|---|---|
| 静态隔离审计 | `_audit.py` | Agent 可见树内无参考实现、无隐藏断言 |
| 逻辑分离（宿主 pytest） | `_logic_check.py` | nop 10 项失败 / oracle 18 项全通过 |
| 容器动态校验 | `_container_check.py` | nop = VALID/0；oracle = VALID/1（18/18） |
| **归档完整性** | `_qc_runs/tools/verify_216_v12_archive.py` | **514 项检查，0 问题** |

## 4. 跑分结果（v1.2.0，14 轮全 VALID）

| 角色 | trial | verdict |
|---|---|---|
| oracle（golden） | `golden-01-cdcb` / `-02-1e1e` / `-03-485c` | **1 / 1 / 1** |
| nop（no-change） | `no-change-01-1c1d` / `-02-b657` / `-03-031c` | **0 / 0 / 0** |
| QWEN 3.8-max | `qwen3.8-max-0902-01-9f15` / `-02-6f1d` / `-03-f5c4` | **0 / 0 / 0** |
| OPUS 5 | `opus-5-01-8806` / `-02-c39f` / `-03-a85d` | **1 / 0 / 1** |
| KIMI K3 | `kimi-k3-01-39dc` | **0** |
| GLM 5.3 | `glm-5.3-01-a108` | **0** |

**门禁判定全部通过**：

| 门禁项 | 要求 | 实测 |
|---|---|---|
| oracle 控制轮 | 3 轮 = 1 | 1/1/1 ✅ |
| nop 控制轮 | 3 轮 = 0 | 0/0/0 ✅ |
| 有效轮数 | QWEN≥3、OPUS≥3、GLM≥1、KIMI≥1 | 3/3/1/1 ✅ |
| **区分度** | **OPUS 总分 > QWEN 总分** | **2 > 0** ✅ |
| run_validity | 全部 VALID | 14/14 ✅ |
| 跑分时身份绑定 | 每轮带 `task_identity.json` | 14/14 ✅ |

跑分时段：2026-10-10 23:56 → 2026-10-11 05:11（本地 runner，Windows 容器）。

QWEN 三轮的失败点集中在 `error-classification`（截断容器须报 `truncated`）与 `streaming`（`iter_records` 必须惰性读取），第 3 轮只跑了 17 turns 便收工（10 项失败），是**合法的 0 分**而非基础设施故障。

## 5. 身份（三种 hash 口径并存）

| 口径 | 值 | 记录位置 |
|---|---|---|
| 平台导入 | `c6b2f869a2a0f19bf305eb940eca72ce357f5de45035d8518e2d2db1bfb6f1e8` | `platform_import.json`（`sha256(instruction.md + Dockerfile + rubric.json + required_testcases.json)`） |
| 整树 | `0c4d44c7201890685d95a0b63d6405c775028c2d7d214cb4ecc654de61c48265` | `jobs/lock.json` |
| runner 跑分 | `f8acb48deb487f5e322c6e241daf49404800d6d1f625576bd5e2552790590214` | 每轮 `agent/task_identity.json` |

镜像：`outside-harbor/wfflab__wchunk-216:1.2.0`，digest `sha256:bf67749c8127580ba588029b56fb6b7ec9567b28cdb4f99808f4eb03245102f5`；
基础镜像 `mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a`。

> 三者的 runner 口径值 `f8acb48d…` 与跑分当时记录的值一致 —— 题包自跑分以来未被改动。

## 6. 交付物

| 文件 | 大小 | sha256 |
|---|---|---|
| `package/wfflab__wchunk-216-v1.2.0-delivery.zip` | 52.7 MiB（390 entries） | `7eb71d90bb1b3e82af71805d9fdfcd6f726759092bf9df22bc9ad2525be098f0` |

## 7. 复现

```powershell
$py = 'C:\Program Files\Python39\python.exe'   # 需要 pytest 的宿主解释器
$env:DOCKER_CONTEXT = 'desktop-windows'
cd deliverables\2026-10-11_wchunk216-返修

# 题包改造（顺序不可颠倒）
& $py -X utf8 _stage1_restructure.py     # 拆分：答案/隐藏断言移出 Agent 可见包
& $py -X utf8 _stage2_agent.py           # 重写题包：离线 Dockerfile / VerifierRoot 判分 / 权重拆分
& $py -X utf8 _stage3_verifier.py        # 判分侧：rubric.conditions.json + SEALED_MANIFEST
& $py -X utf8 _logic_check.py            # 本地逻辑分离校验
docker build -f build\outside_harbor-assets\wfflab__wchunk-216\environment\Dockerfile `
    -t outside-harbor/wfflab__wchunk-216:1.2.0 build\outside_harbor-assets\wfflab__wchunk-216\environment
& $py -X utf8 _container_check.py        # 容器内 oracle/nop 校验
& $py -X utf8 _stage4_metadata.py (docker image inspect outside-harbor/wfflab__wchunk-216:1.2.0 --format '{{.Id}}')

# 跑分（INVALID 自动重跑；每批拿到目标有效轮数才结束）
.\batch_remaining.ps1                    # nop×3 → oracle×3 → OPUS×3 → KIMI×1 → GLM×1
.\run_rounds.ps1 -Mode candidate -Models QWEN -Target 3

# 归档、校验、打包
& 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe' `
    -X utf8 ..\..\_qc_runs\tools\assemble_216_jobs_archive.py
& $py -X utf8 ..\..\_qc_runs\tools\verify_216_v12_archive.py
& $py -X utf8 _package.py

# 清理失效产出（无运行中容器时才可执行）
.\cleanup_failed_runs.ps1
```

## 8. 关于基础设施故障的处置记录（如实留存）

首次 QWEN×3 出现 **3/3 INVALID**（`verifier produced no result.json`）。排查结论：

- 用 `start_container` 同样的两挂载组合反复复现，发现**容器内 `C:\task` 与 `C:\verifier` 同时为空**，而宿主文件完好；`docker inspect` 显示挂载配置正确。
- 裸 `subprocess` 挂载在同一路径上连续 8/8 成功；215 会话在同 runner、同引擎下同一时段成功——**排除题包、挂载参数、python 版本、runner 代码**。
- 结论：**Windows 容器 bind mount 在两个会话并发负载下的间歇性失效**（215 也中过一次 `221521-golden`）。
- 处置：不改共享的 `runner.py`，新增 `run_rounds.ps1`（每轮单独跑、`verdict=INVALID` 自动重跑、拿到目标有效轮数才退出）与 `cleanup_failed_runs.ps1`（带"无运行中容器"安全闸）。重跑批次 **14/14 有效、零 INVALID**。
