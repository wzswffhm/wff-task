# 08 · 多模型验证与稳定性

来源：规范第七章、第八章

---

## 一、冻结条件（8.1）

所有比较必须使用**相同的**：

- Harbor Task 版本
- Harness 版本
- Windows 环境
- 工具权限
- 网络策略
- 资源预算
- 采样配置

> **环境恢复后再开始下一次独立运行。**

---

## 二、主要模型（8.2）

**Qwen3.8-Max-0902 与 Opus 5 每题各独立运行 3 次。**

- 只统计 **VALID** 运行
- **INVALID 必须查明原因并补跑**

### 指标定义

| 指标 | 定义 | 取值范围 |
|---|---|---|
| `model_score_sum` | 同一模型 3 次二值正式分数之和 | **0–3** |
| `testcase_pass_sum` | 同一模型 3 次运行中 required testcase 的 PASS 数量总和 | 仅用于**双方正式分均为 0** 时比较，不形成部分分 |

### 单题准入（满足任一）

```
条件 1：Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum
条件 2：两者 model_score_sum = 0
        且 Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum
```

**不满足准入的情况**：
- 两者正式分和**相同且不全为 0**
- 双方均为 0 但 testcase 表现**没有严格区分**

→ **该题区分度不满足准入要求，应分析后整改或替换。**

### 红线

> **模型门槛不能覆盖数据质量门槛。**
> 即使满足上述分差，存在题面歧义、不可解约束、错误测试、环境故障、薄题、答案泄漏或
> Windows 价值不足时**仍不得验收**。
>
> **不得为制造分差而增加题面未声明要求、错误隐藏测试或冷门单点陷阱。**

---

## 三、辅助模型（8.3）

**GLM-5.3 与 Kimi K3 每题至少完成 1 次有效运行**，主要确认：

1. Agent 能正常进入、读取和修改工作区
2. 构建、测试和结果采集链路可运行
3. 不存在**模型无关**的 infra、权限、依赖或 Verifier 质量问题

**不要求**：
- GLM-5.3、Kimi K3 与 Qwen/Opus 形成固定排名
- 各跑 3 次

**异常处理**：
- 因**题目或基础设施**问题无法完成有效运行 → **必须先修复**
- 属**模型自身能力失败**且运行链路有效 → 可按真实结果记录

---

## 四、Golden / no-change 稳定性（第七章）

### 4.1 同一身份运行（7.1）

Golden、no-change 和模型候选必须使用**同一** base、环境、依赖、测试树、评分规则和资源预算。

> Golden 必须有**直接证据**证明参考解已实际应用，不能只依赖环境变量、任务名称或日志标题。

### 4.2 Golden path（7.2）

干净环境下必须满足：

- 所有 required F2P 与 P2P **执行且 PASS**
- **正式分数为 1**
- **无 SKIP、MISSING、ERROR、旧产物复用或隐藏环境依赖**
- 最终补丁、测试树、环境和日志身份**可以核对**

> Reference Solution **不是天然真值**。若 Golden 与题面冲突、只适配某种内部写法或破坏既有行为，
> 应修复题目、测试或参考解，**不得为保证 Golden=1 而修改题意**。

### 4.3 no-change 与错误反例（7.3）

干净环境下必须满足：

- **P2P 全部通过**
- **至少一个核心 F2P 因目标缺陷失败**
- **正式分数为 0**
- 失败原因**不是**依赖缺失、测试语法、环境未就绪或其他基础设施问题

> 由于采用**全有或全无的二值评分，空跑不得出现非零正式分数。**

除 no-change 外，还应按题目风险验证反例：

- 空实现
- 固定返回
- 提前退出
- 硬编码
- 只修一半
- 吞异常
- 禁用功能

### 4.4 稳定性（7.4）

提交验收前至少完成：

| 检查 | 要求 |
|---|---|
| no-change 独立运行 | **3 次，结果均为 0** |
| Golden 独立运行 | **3 次，结果均为 1** |
| 干净环境重建/恢复复验 | 至少 **1 次** |
| required testcase 集合与终态 | 每次一致，无**非模型原因**抖动 |
| 清理或快照恢复 | **无影响后续运行的残留** |

---

## 五、运行记录归档

位置：`delivery-extras/tasks/<task-id>/model_runs/<model>/`

每次运行须记录：

| 字段 | 说明 |
|---|---|
| 配置 | Task 版本、Harness、环境、工具权限、网络策略、资源预算、采样参数 |
| 真实模型标识 | 精确到版本号 |
| 运行状态 | VALID / INVALID / PENDING / CANCELLED |
| 逐 testcase 结果 | PASS / FAIL / SKIP / MISSING / ERROR / NOT_RUN |
| 轨迹 | 完整 execution trajectory |
| 最终补丁 | 模型产出的 patch |
| 耗时 | 总时长与各阶段 |
| Badcase 归因 | 失败根因分析 |

### 跨运行晋升证据字段

来自 `grade.py` 的 `run_evidence`，用于证明required 3 base + 3 oracle runs：

```
run_id
source_commit
image_digest
log_sha256
spec_sha256
test_patch_sha256
```

> 单份报告无法自证 3+3 次运行；这些字段用于让**跨运行晋升校验器**确认证据完整。

---

## 六、区分度计算示例

```python
# 3 次运行结果
qwen_scores = [0, 1, 0]          # model_score_sum = 1
opus_scores = [1, 1, 1]          # model_score_sum = 3

# 条件 1 成立
assert opus_sum(3) > qwen_sum(1)   # 通过区分度

# 若双 0 场景
qwen_scores = [0, 0, 0]          # model_score_sum = 0
opus_scores = [0, 0, 0]          # model_score_sum = 0
qwen_pass_sum = 12               # 3 次 required PASS 总数
opus_pass_sum = 15               # 条件 2：15 > 12 → 通过区分度
```

---

## 七、自动化执行（`scripts/run_model_validation.py`）

规范要求 4 个模型、共 8 次调用（Qwen 3 + Opus 3 + GLM 1 + Kimi 1）并计算区分度。
手工执行易漏、易算错，统一用脚本完成。

### 7.1 端点与模型

协议均为 **Anthropic Messages**：`POST {base_url}/v1/messages`，
header `x-api-key` + `anthropic-version: 2023-06-01`。

| key | label | base_url | model | 次数 | 角色 |
|---|---|---|---|---|---|
| `qwen3.8-max` | Qwen3.8-Max-0902 | `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic` | `qwen3.8-max` | 3 | primary |
| `opus-5` | Opus 5 | `https://api.blvr.top` | `claude-opus-5` | 3 | primary |
| `glm-5.3` | GLM-5.3 | 同 aliyun | `GLM-5.3` | 1 | auxiliary |
| `kimi-k3` | Kimi K3 | 同 aliyun | `Kimi K3` | 1 | auxiliary |

> ⚠️ aliyun 的 base_url **必须带 `/apps/anthropic` 后缀**；去掉后 `/v1/messages` 返回 404。
> 三个 aliyun 模型共用一个 Key（`HARBOR_WINDOWS_ALIYUN_KEY`），Opus 单独用 `HARBOR_WINDOWS_BLVR_KEY`。

### 7.2 命令

```bash
pip install httpx
export HARBOR_WINDOWS_ALIYUN_KEY=<key>
export HARBOR_WINDOWS_BLVR_KEY=<key>

# 全量
python scripts/run_model_validation.py --tasks <assets> --out delivery-extras/tasks

# 冒烟（每模型 1 次，仅验证连通性）
python scripts/run_model_validation.py --tasks <assets> --out delivery-extras/tasks --smoke

# 平台回填分数后只算区分度
python scripts/run_model_validation.py --score-only --out delivery-extras/tasks
```

可调项：`HARBOR_WINDOWS_MAX_TOKENS` / `TIMEOUT_SEC` / `MAX_RETRIES` / `ENDPOINTS_JSON`。

### 7.3 脚本职责边界（重要）

| 脚本负责 | 脚本**不**负责 |
|---|---|
| 发起 4 模型调用、重试 | 在真实 Windows Runtime 执行 F2P/P2P |
| 保存轨迹、补丁、token、耗时 | 产出正式分（`score`） |
| 区分 VALID / INVALID 并归因 | 判定 Golden / no-change |
| 计算 `model_score_sum` / `testcase_pass_sum` | |
| 给出条件 1 / 条件 2 准入结论 | |

因此 `per_testcase.json` 初值为 `NOT_RUN`、`report.json.score` 初值为 `null`，
**必须由平台 harness（`test.ps1` + `grade.py`）执行后回填**，再跑 `--score-only`。

> 这条分工是刻意设计：规范禁止用 Linux Mock 替代真实 Windows Runtime，
> 故模型调用层与评测执行层必须分离，不能由本脚本伪造分数。

### 7.4 VALID / INVALID 判定

脚本按响应内容自动分类：

| 分类 | 触发 | 结果 | 是否重试 |
|---|---|---|---|
| `credential_rejected` | `API-key is blocked` / `Invalid token` | **INVALID** | 否（重试无意义） |
| `auth_failed` | HTTP 401 / 403 | **INVALID** | 否 |
| `rate_limited` | 429 / `rate limit` | **INVALID** | 是 |
| `quota_exhausted` | `insufficient` / `balance` | **INVALID** | 是 |
| `network_timeout` / `network_error` | 超时 / DNS / SSL | **INVALID** | 是 |
| `model_unavailable` | `model not found` | **INVALID** | 否 |
| `upstream_5xx` | HTTP ≥ 500 | **INVALID** | 是 |
| `model_overloaded` / `context_overflow` | 显式过载/超长 | VALID（按真实结果记录） | 是 |
| 成功 | HTTP 200 | VALID | — |

失效运行会写 `error.json` 与 `badcase_attribution.md`，并在 `meta.json` 标 `retest_required: true`。

### 7.5 准入判定状态机

```
有效运行 < 3            → 待定（blocking: insufficient_valid_runs）
存在 INVALID 未补跑      → 待定（blocking: invalid_runs_not_retested）
3 次有效但分数未回填     → 待定（blocking: scores_not_filled）
─────────────────────────────────────────────
否则按条件 1 / 条件 2 判定 → True / False
```

> `--score-only` 退出码：`0` 无明确失败（含"待定"）／`1` 存在明确"不通过"。
> 把"待定"与"不通过"分开，是为了避免"分数还没回填"被误报成"区分度不合格"。

### 7.6 输出

```
delivery-extras/
├── model_summary.csv                # 各模型 runs/valid/invalid/score_sum
├── model_validation_report.md       # 区分度准入表 + 逐模型状态
├── model_validation_summary.json    # 机器可读
└── tasks/<task-id>/model_runs/<model>/run-N/
    ├── meta.json                    # 状态/耗时/token/归因/retest_required
    ├── response.md                  # 原始回复
    ├── patch.diff                   # 提取的补丁
    ├── per_testcase.json            # 逐 testcase（待平台回填）
    ├── report.json                  # 正式分（待平台回填）
    └── badcase_attribution.md       # 失败归因
```

### 7.7 权限配置模板

`scripts/model_endpoints.template.json` 提供端点和凭据字段模板。
复制为 `model_endpoints.local.json` 并填 Key（该名已在 `.gitignore` 中，不会入库）。

---

## 八、多模型自检

```
[ ] Qwen3.8-Max-0902 独立运行 3 次（全 VALID）
[ ] Opus 5 独立运行 3 次（全 VALID）
[ ] model_score_sum 计算正确
[ ] 区分度满足（条件 1 或条件 2）
[ ] 无 INVALID 未补跑
[ ] GLM-5.3 ≥1 次有效运行
[ ] Kimi K3 ≥1 次有效运行
[ ] 无模型无关 infra/权限/依赖/Verifier 故障
[ ] Golden 3×1，无 SKIP/MISSING/ERROR/旧产物
[ ] no-change 3×0，P2P 全过 + 核心 F2P 失败
[ ] 至少 1 次干净重建/恢复复验
[ ] 运行记录与证据字段齐全
[ ] 正式分已由平台 harness 回填（非脚本伪造）
```
