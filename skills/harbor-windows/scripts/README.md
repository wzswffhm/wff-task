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
