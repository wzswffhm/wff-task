# scripts/ 脚本说明

全部脚本仅用标准库 + `httpx`（多模型验证需要）。建议用隔离 venv 运行：

```bash
python -m venv ~/.workbuddy/binaries/python/envs/default
~/.workbuddy/binaries/python/envs/default/Scripts/pip install httpx
```

（Windows 路径：`C:\Users\<user>\.workbuddy\binaries\python\envs\default\Scripts\python.exe`）

---

## 1. `validate_package.py` — 题包校验

按验收门禁做结构与身份一致性校验，输出 `PASS` / `FAIL` / `FLAG`。

```bash
python validate_package.py --package <题包根目录> --schema-version 1.3
python validate_package.py --package <题包根目录> --json validate-report.json
```

| 检查类别 | 内容 |
|---|---|
| 结构 | 标准 Harbor 五件套是否齐全 |
| task.toml | `version` / `[metadata]` / `[agent]` / `[verifier]` / `[environment]` / 资源 / 12h 上限 |
| 题面泄漏 | Golden Patch / Oracle / 隐藏测试 / F2P-P2P / Reward 关键词 |
| 环境泄漏 | `environment/` 内是否混入 Solution 或答案 |
| tests | 验证入口、INVALID 区分能力、二值判分、旧 `judge.toml`/`rubric.json` 残留 |
| spec | `swelive_spec.json` 的 F2P/P2P 与 `verification_evidence` |
| 身份 | `harbor/` 与 `harbor-assets/` 的 task_id 一一对应、镜像引用一致 |
| 伴随材料 | 批次级 7 文件 + 题级 6 项 |
| 镜像 | 是否另存不可变 Digest |

退出码：`0` 全过（可能含 FLAG）／`1` 存在 FAIL／`2` 参数错误。

---

## 2. `build_delivery_extras.py` — 伴随材料骨架

```bash
# 批量
python build_delivery_extras.py --assets outside_harbor-assets --out delivery-extras
# 单题
python build_delivery_extras.py --assets outside_harbor-assets --out delivery-extras \
    --task-id Azure__azure-sdk-for-python-41822
# 预览
python build_delivery_extras.py --assets outside_harbor-assets --out delivery-extras --dry-run
```

生成批次级 7 文件 + `EXTERNAL_IMAGES.json` + 每题 `metadata/`（4 个 JSON）、
`evidence/`（5 类）、`model_runs/`（4 个模型）、`testcase_mapping.csv`、
`quality_review.md`、`remediation_and_retest.md`。

> **已存在的文件不会被覆盖**。所有 `TODO` / `PENDING` 必须人工补齐，否则不得验收。

---

## 3. `run_model_validation.py` — 多模型自动化验证

按规范第七、八章执行多模型验证并计算区分度准入。

```bash
# 完整跑（Qwen 3 次 + Opus 3 次 + GLM 1 次 + Kimi 1 次）
python run_model_validation.py --tasks outside_harbor-assets --out delivery-extras/tasks

# 连通性冒烟（每模型 1 次）
python run_model_validation.py --tasks outside_harbor-assets --out delivery-extras/tasks --smoke

# 只建骨架不调用
python run_model_validation.py --tasks outside_harbor-assets --out delivery-extras/tasks --dry-run

# 平台跑完测试、回填 report.json 分数后，只算区分度
python run_model_validation.py --score-only --out delivery-extras/tasks
```

### 默认模型配置

| key | label | 端点 | 模型名 | 次数 | 角色 |
|---|---|---|---|---|---|
| `qwen3.8-max` | Qwen3.8-Max-0902 | aliyun MaaS `/apps/anthropic` | `qwen3.8-max` | 3 | primary |
| `opus-5` | Opus 5 | `api.blvr.top` | `claude-opus-5` | 3 | primary |
| `glm-5.3` | GLM-5.3 | aliyun MaaS `/apps/anthropic` | `GLM-5.3` | 1 | auxiliary |
| `kimi-k3` | Kimi K3 | aliyun MaaS `/apps/anthropic` | `Kimi K3` | 1 | auxiliary |

协议均为 **Anthropic Messages**（`POST {base_url}/v1/messages`，header `x-api-key` + `anthropic-version: 2023-06-01`）。

### 凭据管理（推荐用环境变量）

```bash
export HARBOR_WINDOWS_ALIYUN_KEY=<aliyun key>   # 供 qwen / glm / kimi 共用
export HARBOR_WINDOWS_BLVR_KEY=<blvr key>       # 供 opus
```

或复制 `model_endpoints.template.json` → `model_endpoints.local.json` 填 Key，
然后 `--config model_endpoints.local.json`（该文件名已在 `.gitignore` 中）。

> ⚠️ **不要把明文 Key 提交到仓库。**

### 可调环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `HARBOR_WINDOWS_MAX_TOKENS` | 8192 | 单次响应上限 |
| `HARBOR_WINDOWS_TIMEOUT_SEC` | 600 | 单次请求超时 |
| `HARBOR_WINDOWS_MAX_RETRIES` | 3 | 重试次数（凭据/模型类错误不重试） |
| `HARBOR_WINDOWS_ENDPOINTS_JSON` | — | 指向配置文件 |

### 区分度准入

```
条件 1: Opus5.model_score_sum > Qwen.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum
```

- 只统计 **VALID** 运行；**INVALID 必须查明原因并补跑**，不得计入难度统计
- `--score-only` 退出码：`0` 无明确失败／`1` 存在明确不通过（待定不算失败）

### 输出

```
delivery-extras/
├── model_summary.csv                  # 各模型汇总
├── model_validation_report.md         # 区分度准入报告
├── model_validation_summary.json      # 机器可读汇总
└── tasks/<task_id>/model_runs/<model>/run-N/
    ├── meta.json                      # 状态/耗时/token/归因
    ├── response.md                    # 模型原始回复
    ├── patch.diff                     # 从回复提取的补丁（若可提取）
    ├── per_testcase.json              # 逐 testcase 结果
    ├── report.json                    # 正式分（待平台回填）
    └── badcase_attribution.md         # 失败归因（失败时）
```

### ⚠️ 脚本与平台 harness 的分工

本脚本是**模型调用与记录层**，不是评测沙箱：

- 它负责：发起调用、保存轨迹与补丁、区分 VALID/INVALID、计算区分度
- 它**不负责**：在真实 Windows Runtime 中执行 F2P/P2P 测试

因此每次运行产出的 `per_testcase.json` 初始为 `NOT_RUN`、`report.json.score` 为 `null`。
**正式分数必须由平台 harness（`test.ps1` + `grade.py`）执行后回填**，
再跑 `--score-only` 得出区分度结论。

这一分工是为了保证"不得用 Linux Mock 替代真实 Windows Runtime 验证"这条红线。

---

## 4. `build_jobs.py` — 生成交付 `jobs/` 目录

平台交付结构要求题包（组装批次包时为 `outside_harbor-assets/`，与 `<task-id>/` 平级）下
有 `jobs/`，每次跑分作业一个 `<job-id>/`：

```text
jobs/<job-id>/
├── job.json            # 身份 + 结果 + 来源指针
├── agent/run.json      # 模型侧（控制组不经过 agent）
└── verifier/result.json# 判定结论 + 原始日志 sha256
```

```bash
python build_jobs.py --task-dir ../../harbor-windows/wfflab__wreparse-217 \
    --summary ../../deliverables/2026-10-07_wreparse217-交付/evidence/model_runs_summary_r12.json
# 附带本机判分链路复核证据（可选）
python build_jobs.py --task-dir <题包> --summary <汇总 json> --local-verification <目录>
# 预览
python build_jobs.py --task-dir <题包> --summary <汇总 json> --dry-run
```

| 行为 | 说明 |
|---|---|
| 唯一事实来源 | `summarize_model_runs.py` 的汇总输出；副本写入 `jobs/_index/qualification_summary.json` |
| job-id | runner 的 `run_id`，与汇总一一对应；重复即报错退出 |
| 剔除轮 | `agent_status ∈ {error, no_tool_call}` 的轮**保留但不计分**，标 `excluded` + 原因 |
| 缺口声明 | 原始 `agent.log` / `test.log` / `checks.json` 未留存时，不伪造；在 `agent/run.json` 与 `jobs/README.md` 显式声明 |
| 凭据扫描 | 生成后扫描 `sk-` / Bearer / `x-api-key` / 凭据赋值；命中则 exit=2 |

> `jobs/` 不得含 `solution/`、答案、隐藏用例或凭据。

---

## 5. `package_task_zip.py` — 打交付 ZIP

ZIP 根 = `<task-id>/`，含 `instruction.md` / `task.toml` / `source.json` / `environment/**` /
`tests/**`（含 `required_testcases.json`）/ **`solution/**`** / `jobs/**`；
**只排除** `extras/`、`__pycache__/`、`.pytest_cache/`、`*.pyc`、`.DS_Store`。

> ⚠️ 甲方 `windows-harbor-qc` checklist 第 1 节明确要求 `solution/`（Golden 入口）、`source.json`、
> `tests/required_testcases.json` **必须随题包交付**。**不要**再把 `solution/` 或 `source.json` 排除——
> 那会让甲方 QC 静态检查直接 FAIL（`missing top-level solution` / `missing top-level source.json`），
> 且静态不过就不会进入 Oracle/NOP 动态测试。

```bash
python package_task_zip.py --task-dir ../../harbor-windows/wfflab__wreparse-217 \
    --out-dir <输出目录> --verify
python package_task_zip.py --task-dir <题包> --out-dir <输出目录> --no-jobs   # 不含 jobs
```

- 版本号取 `task.toml` 的 `[task].version`（不是顶层 schema `version`），文件名形如 `<task-id>-v<version>.zip`
- `--verify`：解包后逐文件比对 SHA256，并报告缺文件/哈希不符
- **打包前自检**：缺 `source.json`、`solution/README.md`、`solution/solve.*`、`tests/required_testcases.json`
  即 exit=2 拒发；ZIP 内混入 `extras/` 或 `*.pyc` 同样拒发

---

## 6. `build_required_testcases.py` — 生成甲方 QC 必备的 testcase 清单

甲方 QC 要求 `tests/required_testcases.json` 是**非空、id 唯一、同时含 F2P 与 P2P** 的列表：

```json
[{"id": "sample-verifies", "group": "F2P"}, {"id": "verify-never-raises", "group": "P2P"}]
```

分组必须来自题包**既有证据**，不得臆造。两种来源：

```bash
# A) 用「未打补丁」与「Golden」两端逐项 checks.json 对比
python build_required_testcases.py --task-dir <题包> \
    --from-checks <candidate checks.json> <golden checks.json> --write

# B) 用平台导入包里的 swelive_spec.json
python build_required_testcases.py --task-dir <题包> \
    --from-spec <swelive_spec.json> --write
```

| 来源 | 判定规则 |
|---|---|
| `--from-checks` | `candidate=FAIL 且 golden=PASS` → **F2P**；`两端都 PASS` → **P2P**；其他组合直接报错拒生成 |
| `--from-spec` | 读 `FAIL_TO_PASS` / `PASS_TO_PASS`（pytest node id），归一化为 rubric 短 id（去 `test_`、`_`→`-`） |

- 输出顺序固定按 `tests/rubric.json` 的 `items[].test_ids` 展开顺序，稳定可复现
- 自校验：rubric 里的 testcase 缺分组依据、或分组依据含 rubric 未声明的 testcase、或某一类为空 → 拒绝写入
- **与 `task_hash` 无关**：`task_hash` 公式只含 instruction / test_patch / oracle_patch / Dockerfile，
  新增本清单**不会**改变 `task_hash`，因此无需重跑模型轮验证

---

## 7. `align_report_protocol.py` — 对齐甲方 QC 的报告协议

甲方 `windows-harbor-qc` 的 `run_trials.py: formal_result` 只认三套报告协议，其中与本项目
结构契合的是 **aggregate-v1**（`run_trials.py:57-84`），硬性要求：

| 要求 | 说明 |
|---|---|
| `report.schema_version == "aggregate-v1"` | 协议判定入口 |
| `report.run_validity == "VALID"` | 否则直接判 INVALID（不得把证据不全当作 0 分） |
| `total / passed / failed / invalid` 均为 int 且 `invalid == 0` | 计数须与 `cases` 自洽 |
| `formal_score == int(passed == total)` | 且必须与 Harbor 的 reward 一致 |
| `cases == [{"test_id": "f2p-…"\|"p2p-…", "passed": bool}]` | 覆盖 rubric 声明的全部 testcase |
| **`rubric.items[].test_ids` 每项都以 `f2p-`/`p2p-` 开头** | `run_trials.py:74` 硬校验 |

本脚本负责纯数据改动（不碰 PowerShell 逻辑）：

```bash
python align_report_protocol.py --task-dir <题包> \
    --from-checks <candidate checks.json> <golden checks.json> --write
python align_report_protocol.py --task-dir <题包> --from-spec <swelive_spec.json> --write
```

- 给 `tests/rubric.json` 的 `test_ids` 统一加 `f2p-`/`p2p-` 前缀（幂等），并重建 `required_testcases.json`
- **同步 `tests/judge.toml` 的 `source_sha256`** —— 否则甲方静态检查报 "judge.toml rubric hash
  does not match rubric.json"（`run_qc.py:246-252`）
- 配套要求：聚合脚本 `tests/aggregate_results.ps1` 必须**剥前缀**去匹配 `checks.json` 的裸 id，
  并输出 aggregate-v1 字段；`tests/test.ps1` 需在 Harbor 环境下把报告与 reward 三件套写入
  平台的 verifier 日志目录（本仓库 217/215 已按此改好，可作参考实现）

### ⚠️ `.ps1` 必须保持纯 ASCII

Windows PowerShell 5.1 **按 ANSI 解码无 BOM 的 `.ps1`**：UTF-8 中文注释会字节错位，
严重时**吞掉行尾换行**，使下一行代码被并入注释行（症状是某变量莫名成 `$null`、
`ContainsKey` 抛 "键不能为 null"）。题包内所有 `.ps1` 一律只写 ASCII 注释 —— 本次已踩坑。
