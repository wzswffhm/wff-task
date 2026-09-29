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

## 七、多模型自检

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
```
