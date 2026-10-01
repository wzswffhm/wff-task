# Harbor Windows 题包验证流程

> 依据：《Windows 专项 Coding Bench 数据采购》规范第三章（Windows 准入）、第七章（Golden/no-change 稳定性）、
> 第八章（多模型验证）、第十/十一章（验收与一致性）。
> 对应 skill `harbor-windows` 的 `references/06-acceptance-gates.md` 与 `references/08-model-validation.md`。
>
> **本目录为平铺布局**：9 个题包各自独立成 `<task-id>/` 子目录，无批次层；
> 跨题汇总在 `_index/`。下文路径均以 `harbor-windows/` 为基准。

---

## 一、三层验证总览

| 层 | 验证什么 | 需要模型？ | 执行者 | 主要产物 |
|---|---|---|---|---|
| **L1 结构校验** | 五件套齐全、Schema 合法、身份三元组全链一致、无答案泄漏 | 否 | `scripts/validate_package.py` | `validate-report.json` |
| **L2 判分正确性** | 二值判分是否可信：Golden 必 1、no-change 必 0、错误实现必 0、多解可接受 | 否 | 真实 Windows Runtime 跑 `tests/test.ps1` | `<task-id>/extras/evidence/` |
| **L3 多模型区分度** | 题目对强/弱模型是否有区分力，且无模型无关的基础设施故障 | **是**（4 个模型） | `scripts/run_model_validation.py` + 平台 harness | `<task-id>/extras/model_runs/` |

**关键边界**：L2 必须在**真实 Windows Runtime** 里执行，禁止用 Linux Mock 替代（一票否决第 1、6 条）。
L3 的脚本只是**模型调用层**，它不产出正式分——正式分必须由平台 harness（`test.ps1` + `grade.py`）执行后回填。

---

## 二、环境与软件支持

### 2.1 评测环境（镜像内，必须真实 Windows）

| 项 | 要求 | 本题实际值 |
|---|---|---|
| 操作系统 | Windows Server Core 容器（**不能是 Linux 容器**） | `mcr.microsoft.com/windows/servercore:ltsc2022` |
| Python | 版本锁定 | **3.12.9**（官方 embed amd64 包） |
| pytest | 版本锁定 | **8.3.5** |
| pytest-json-report | 版本锁定，出机器可读报告 | **1.5.0** |
| Git | 补丁捕获与回放 | 构建期经 Chocolatey 安装 |
| PowerShell | 运行 `test.ps1` | 5.1+（镜像自带） |
| 资源预算 | 见 `task.toml` | 4 CPU / 8 GB 内存 / 20 GB 存储 |
| 超时 | agent 21600s；verifier 3600s | 同左 |
| 网络 | 构建期可联网；**评测期应断网** | 依赖已全部预装 |

> **版本必须三处一致**：镜像 `Dockerfile`、本机验证环境、`task.toml` 声明。任一处漂移都可能导致判分结果不可复现。

### 2.2 承载平台（宿主）

- **Docker Desktop / Docker Engine，且已切换到 Windows 容器模式**
  （Windows 10/11 Pro/Enterprise 或 Windows Server；Linux 容器模式**无法**构建该镜像）
- 磁盘余量 ≥ 20 GB（Server Core 基础层较大）

### 2.3 本机对照验证环境（不依赖 Docker）

用于在写题阶段快速确认判分逻辑，**必须使用与镜像相同的 pytest 版本**：

- Windows 11 + Python 3.13（本机）
- `pytest==8.3.5`、`pytest-json-report==1.5.0`
- 本机默认 NTFS 语义（**不得**对测试目录开启按目录大小写敏感 `fsutil file setCaseSensitiveInfo`）

### 2.4 模型调用环境

- Python + `httpx`
- 协议：**Anthropic Messages**，`POST {base_url}/v1/messages`
  header：`x-api-key` + `anthropic-version: 2023-06-01`
- 凭据经环境变量注入，**不入库**（本题凭据存仓库外 `~/.workbuddy/harbor-windows.env`）

---

## 三、需要的模型

| 角色 | 模型 | 独立运行次数 | base_url | model 名 | 凭据环境变量 |
|---|---|---|---|---|---|
| 主要 | **Qwen3.8-Max-0902** | **3** | `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic` | `qwen3.8-max` | `HARBOR_WINDOWS_ALIYUN_KEY` |
| 主要 | **Opus 5** | **3** | `https://api.blvr.top` | `claude-opus-5` | `HARBOR_WINDOWS_BLVR_KEY` |
| 辅助 | **GLM-5.3** | **1** | 同 aliyun | `GLM-5.3` | `HARBOR_WINDOWS_ALIYUN_KEY` |
| 辅助 | **Kimi K3** | **1** | 同 aliyun | `Kimi K3` | `HARBOR_WINDOWS_ALIYUN_KEY` |

合计 **8 次调用**。

> ⚠️ aliyun 的 base_url **必须带 `/apps/anthropic` 后缀**，去掉后 `/v1/messages` 返回 404。
> 三个 aliyun 模型共用一个 Key。

**冻结条件**：所有比较必须使用相同的 Task 版本、Harness 版本、Windows 环境、工具权限、网络策略、资源预算与采样配置；**每次运行之间必须恢复环境**。

**辅助模型的作用**：只确认 ①Agent 能正常进入/读取/修改工作区 ②构建、测试、结果采集链路可运行 ③不存在模型无关的 infra/权限/依赖/Verifier 缺陷。
不要求 GLM/Kimi 与 Qwen/Opus 形成固定排名，也不要求各跑 3 次。

---

## 四、判分链路（`tests/test.ps1` → `tests/grade.py`）

题包内判分是**全有或全无的二值评分**：required F2P + P2P 全过 = **1**，否则 = **0**，异常 = **INVALID**。

`test.ps1` 的执行顺序：

| 步 | 动作 | 失败时 |
|---|---|---|
| 1 | 校验工作区身份（`task_id` / base commit） | `===SWELIVE_INVALID ...===`，exit 2 |
| 2 | 校验并应用隐藏测试补丁 `tests/test_patch.diff` | `swelive_invalid test_patch_apply_failed`，exit 2 |
| 3 | 环境预检 `python -c "import pytest, wsync"` | `swelive_invalid prepared_environment_missing`，exit 2 |
| 4 | 跑 `pytest --json-report` 产出 `reports/pytest-results.json` | 报告缺失 → INVALID |
| 5 | 把原始日志按 `===SWELIVE_LOG_BEGIN/END===` 包裹输出 | — |
| 6 | 调用 `grade.py` 解析日志并生成 reward 产物 | reward 缺失/畸形 → INVALID |

**两条易错点（已在骨架修正）**：
- pytest 退出码 **1 = 存在测试失败 = 候选的合法 0 分**，只有 `> 1`（编译/收集失败）才是候选级故障 → 判据用 `$testRc -gt 1`，不能用 `-ne 0`；
- `log_parser` 必须兼容 `pytest-json-report` 的**多行** JSON 输出。

**INVALID 与 0 分严格区分**：环境、Runner、权限、依赖或 Verifier 缺陷**不得**被记成模型 0 分（一票否决第 8 条）。

### 关于裁判模型：本线**不需要**，且明令禁止

| 角色 | 是什么 | 本线是否需要 |
|---|---|---|
| **裁判模型（LLM / Agent Judge）** | 用大模型给候选答案打主观分 | ❌ **禁止**——一票否决第 7 条 |
| **被测模型（考生）** | Qwen3.8-Max / Opus 5 / GLM-5.3 / Kimi K3，产出补丁 | ✅ 需要，但**只作为被评测对象**，不参与打分 |
| **平台 harness** | 执行 `test.ps1` + `grade.py` 的评测执行层，非模型 | ✅ 需要 |

判分完全由 **pytest 断言**决定，`grade.py` 只用 Python 标准库。
禁止的判定方式还包括：字符串/正则匹配、代码 Diff、文件存在性、模型自报（一票否决第 6 条）。

**原因**：本线要的是**确定性**——no-change 独立 3 次全 0、Golden 独立 3 次全 1。
LLM 裁判主观、不可复现、可被 prompt 操纵，无法支撑这种稳定性门禁。

> **口径差异（勿混用）**：`harbor-windows` 为二值判分、无裁判模型；
> `harbor-rl` / `harbor-weakness`（法律/金融）使用 rewardkit 的 LLM judge（含 likert 1–5 归一化）；
> `harbor-16` 走 pytest 程序化评分。三条线的判分口径不同，同一批次内不得混用。

---

## 五、逐步验证流程

### 阶段 A —— 结构校验（无需模型，秒级）

```bash
# 平铺模式：自动识别本目录下每个含 task.toml 的题包
python skills/harbor-windows/scripts/validate_package.py \
    --package harbor-windows --schema-version 1.3
```

检查项：五件套齐全、Schema 合法、F2P/P2P 声明与 `grade.py` 引用一致、身份三元组
（`task_id` + `task_version` + `task_hash`）在 `task.toml` / `swelive_spec.json` / `platform_import.json` / `manifest.json` 四处一致、
镜像引用一致、题级 `extras/` 六项齐全、目录级 `_index/` 七文件齐全、`EXTERNAL_IMAGES.json` 含 digest。

**期望**：`PASS=256`、`FAIL=0`、`FLAG=0`，退出码 `0`。

### 阶段 B —— 判分正确性矩阵（无需模型，必须真实 Windows 执行）

| 编号 | 场景 | 次数 | 期望 |
|---|---|---|---|
| B1 | **no-change**（原样不改） | 独立 **3** | 每次 **0**；P2P 全过 + 至少一个核心 F2P 失败 |
| B2 | **Golden**（应用 `solution/oracle.patch`） | 独立 **3** | 每次 **1**；无 SKIP / MISSING / ERROR / 旧产物复用 |
| B3 | **错误反例矩阵** | 按风险各 1 | 全 **0**（空实现 / 固定返回 / 提前退出 / 硬编码 / 只修一半 / 吞异常 / 禁用功能） |
| B4 | **等价实现**（不同 API + 不同控制流） | ≥1 | **1** —— 证明测试接受合理多解，不绑定 Golden 私有写法 |
| B5 | **干净重建/恢复复验** | ≥1 | 清空全部中间产物后重跑，B1/B2 结论不变，无残留影响后续运行 |
| B6 | **Hack 审查** | — | 联网取答案 / 读本地 Solution / 篡改测试或评分 / 复用旧产物，按四层分级记录 |

> B3 的"只修一半"很关键：本题三条缺陷必须**全部**修好才得分，只修其中一两条实测均为 0。

### 阶段 C —— 多模型区分度（需要 4 个模型）

```bash
pip install httpx
export HARBOR_WINDOWS_ALIYUN_KEY=<aliyun key>
export HARBOR_WINDOWS_BLVR_KEY=<blvr key>

# C1 冒烟：每模型 1 次，仅验连通性
python skills/harbor-windows/scripts/run_model_validation.py \
    --tasks harbor-windows --out harbor-windows --layout flat --smoke

# C2 全量：Qwen×3 + Opus×3 + GLM×1 + Kimi×1
python skills/harbor-windows/scripts/run_model_validation.py \
    --tasks harbor-windows --out harbor-windows --layout flat

# C3 平台 harness 回填正式分后，只算区分度
python skills/harbor-windows/scripts/run_model_validation.py \
    --score-only --out harbor-windows --layout flat
```

> `--layout flat` 让 `model_runs/` 落进各题的 `<task-id>/extras/`，
> 汇总（`model_summary.csv` 等）落进 `_index/`。批次布局（默认 `--layout batch`）行为不变。

**C2 之后**：`per_testcase.json` 初值为 `NOT_RUN`、`report.json.score` 为 `null`，
必须把每个模型产出的 `patch.diff` 投入平台 harness（真实 Windows Runtime）跑出正式分并回填，再执行 C3。

**区分度准入（满足任一）**：

| 条件 | 内容 |
|---|---|
| 条件 1 | `Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum`（各自 3 次二值分之和，0–3） |
| 条件 2 | 两者 `model_score_sum` 均为 0，且 `Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum` |

不满足 → 该题**区分度不达准入**，须分析后整改或替换（一票否决第 13 条）。

**状态机**：有效运行 <3 / 存在 INVALID 未补跑 / 分数未回填 → 一律**待定**（blocking），不得误报成"不通过"。

**红线**：模型分差**不能覆盖**数据质量门槛；禁止为制造分差而增加题面未声明的要求、错误隐藏测试或冷门单点陷阱。

### 阶段 D —— 冻结与归档

- 镜像构建后另存 **Digest**（镜像 tag **不是**不可变身份）
- 归档每次运行的：配置、真实模型标识、状态、逐 testcase 结果、轨迹、最终补丁、耗时、badcase 归因
- 生成 `checksums.sha256`，并确认 Git 冻结版本可定位

---

## 六、当前进度（9 题）

| 项 | 状态 | 说明 |
|---|---|---|
| L1 结构校验 | ✅ 通过 | `PASS=256 FAIL=0 FLAG=0`，退出码 0（平铺模式，9 题全覆盖；459 条 checksums 复算一致） |
| B1–B5（`wfflab__wsync-142`） | ✅ 通过 | no-change ×3 均 0；Golden ×3 均 1；4 个反例均 0；等价实现得 1；干净重建复验一致 |
| B1–B5（其余 8 题） | ⏳ **未执行** | 按要求「先不跑测试」，只完成题目构造（base repo / 隐藏测试 / 参考解 / 交付结构）与静态校验 |
| **镜像 Digest** | ⏳ **待补** | 9 个镜像均未构建，`image_digest = PENDING_BUILD`（未伪造） |
| **L3 多模型区分度** | ⏳ **待补** | 按要求暂未执行；Opus 端点凭据亦未提供 |

> 缺口与整改建议见 `_index/known_issues.md`（K1–K9）与 `_index/validation_report.md`。
> `wfflab__wsync-142` 的证据（原始日志、`report.json`、reward 产物）归档于
> `wfflab__wsync-142/extras/evidence/`。

---

## 七、一票否决速查（与验证流程直接相关者）

| # | 否决项 |
|---|---|
| 1 | 未在真实目标 Windows Runtime 判分 |
| 3 | Golden 无法稳定得 1，或 no-change 无法稳定得 0 |
| 4 | P2P 在 base 失败、F2P 与目标缺陷无关，或 required testcase 缺失/跳过却被计分 |
| 6 | 核心功能主要靠字符串、正则、代码 Diff、文件存在、模型自报或 Linux Mock 判定 |
| 7 | 使用权重、部分分、LLM/Agent Judge 或主观软质量分 |
| 8 | 环境/Runner/权限/依赖/Verifier 缺陷被记为**模型 0 分** |
| 13 | 不满足模型区分度要求，整改后仍无有效区分 |

完整 14 条见 `skills/harbor-windows/references/06-acceptance-gates.md`。
