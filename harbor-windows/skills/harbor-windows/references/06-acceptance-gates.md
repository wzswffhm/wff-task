# 06 · 验收门禁（一票否决 + DoD + 验收层级）

来源：规范第七章、第十章、第十一章

---

## 零、跑分前置门（硬性 · 最先执行 · 2026-10-12 起）

**本节在流程顺序上先于其余各节**：它是**唯一一道在花掉模型预算之前**执行的验收门。

### 规则

1. 在真实 Windows Runtime 中开跑**任何**一轮之前（环境验证 / Golden / no-change / 模型验证），
   必须先对待交付形态的题包执行甲方 `windows-harbor-qc` 自检，且**退出码必须为 `0`（PASS）**。
2. 退出码 `1`（FAIL）或 `2`（BLOCKED）时**一律禁止开跑**：先修包 → 重新自检 → 直到 PASS。
3. 自检对象必须是**交付 ZIP**，不是源码目录 —— 只有 ZIP 形态才等价于甲方真正拿到的那份包。
4. 自检 PASS 后题包内容**冻结**；跑分期间只允许新增 `jobs/` 与 `extras/`。

### 必须 PASS 的四类门

| 门 | 判据 |
|---|---|
| 交付布局门 | `environment/adapter.toml` 可被 TOML 解析；`environment/` 七个必备脚本齐全；ZIP 内层根目录名 = `<task_id>-v<版本>-delivery`；不得手改目录名 |
| Harbor 静态门 | 五件套齐全；`.ps1` / `.bat` 内被引用的路径真实存在；无自定义必需字段；无 Solution / 隐藏 Tests / 凭据泄漏 |
| jobs 门 | 每个 job 必备文件齐全：`config.json`、`lock.json`、`result.json`、`trial.log`、`artifacts/manifest.json`、`verifier/{result.json,reward.txt,test-stdout.txt,verifier.log}`；模型轮另需 `agent/model-result.json` + `agent/trajectory.jsonl`；Oracle 轮另需 `agent/oracle.txt` + `agent/qc-oracle-application.json` |
| 身份门 | 全部 job 的 `task_checksum` = 交付包的 **Harbor dirhash** |

> 判分证据（`verifier/result.json` 的协议字段、有效性、二值分数、testcase 集合）以自检脚本
> `report.md` 的报错为准，**不要凭记忆自拟协议字段名**。

### 已知差异：`task.toml` 不写 `docker_image`（2026-10-13 起）

**规范**：基础镜像只在 `environment/Dockerfile` 的 `FROM` 里声明，并 pin 到不可变
digest（禁止 `latest`）；`task.toml` **不得**写 `docker_image`。

**差异**：随包下发的甲方 QC（`scripts/run_qc.py` 里 `docker_image` 的取值与判空段）
仍把该字段当作 `task.toml` 的必需项 —— 缺失即写 `task.toml has no docker_image`，
把"静态结构"判为 `FAIL`，`run_qc.py` 退出码 `1`。

**处理**：这条静态 FAIL **属预期**，不要为过检查把字段写回去。做法是：

- 交付说明里显式记录该差异，并引用本节
- 其余静态项与**全部动态项**（Oracle / NOP 控制跑）必须仍然 PASS
- 甲方更新工具包后该 FAIL 自然消失

> 两个配套坑：
> 1. `run_qc.py` 的 `--attempts` 最小为 `3`；传 `1` 会在 argparse 阶段直接退出，
>    日志里只留下 `--attempts must be at least 3`，极易误判成"容器跑不起来"。
> 2. **Harbor 侧不受影响**：`harbor/environments/definition.py` 的
>    `should_use_prebuilt_docker_image()` 在 `docker_image` 为空时返回 `False`，
>    `has_agent_environment_definition()` 也把 `environment/Dockerfile` 当作合法定义，
>    于是 Harbor 自动回落到 Dockerfile 构建；`--force-build` 只是排除缓存的额外保险。

### 冻结铁律

Harbor dirhash 覆盖除顶层 `jobs/` 以外的**全部**文件。因此：

- ✅ 跑分**之后**组装 `jobs/` 是安全的（不改变 checksum）
- ❌ 跑分**之后**动 `task.toml` / `instruction.md` / `environment/` / `solution/` /
  `tests/` / `verifier/` 的任何一个字节 → 全部 `task_checksum` 失效，**必须整批重跑**

**顺序恒为**：定稿 → 预打包 → 自检 PASS → 冻结 → 跑分 → 组装 `jobs/` → 交付。

### 违反即一票否决

见第一节第 **15** 条 —— **未经甲方自检 PASS 即开跑**，或**跑分后修改题包内容**。

> **实例（2026-10-12）**：218 号包跑满 14 轮（8 轮模型 + 6 轮对照）后，甲方自检仍 FAIL ——
> `adapter.toml` 第 38 行 TOML 非法、`solution/reference/wlogseg` 与
> `tests/test_wlogseg_semantics.py` 被脚本引用却不存在、job 缺 `lock.json` /
> `verifier/verifier.log` / `artifacts/manifest.json`、`task_checksum` 与交付包不符。
> 这些**全部**在跑第一轮之前就能查出来。215 v2.1.0 与 216 v1.2.0 也带着同一个
> `adapter.toml` 缺陷交付。三个包的既有结论归档在
> `harbor-windows/_qc_runs/qc-{215,216,218}-auto/`。

---

## 一、17 条一票否决

出现任一情况，单题**不得进入正式集**：

| # | 否决项 |
|---|---|
| 1 | Windows 反事实判定不通过（**含新增机制门禁 F1–F6：缺门禁产物、机制无题面/F2P 锚点、包内出现自我否认 Windows 价值的表述**），或未在**真实目标 Windows Runtime** 判分 |
| 2 | 题面不可解、关键约束缺失，或实际下发内容与验收要求不一致 |
| 3 | Golden 无法稳定得 1，或 no-change 无法稳定得 0 |
| 4 | P2P 在 base 失败、F2P 与目标缺陷无关，或 required testcase 缺失/跳过却被计分 |
| 5 | testcase 与题面冲突、增加未声明要求、误杀合理多解，或绑定 Golden 私有写法 |
| 6 | 核心功能主要依靠**字符串、正则、代码 Diff、文件存在、模型自报或 Linux Mock** 判定 |
| 7 | 使用 testcase **权重、部分分、LLM/Agent Judge** 或主观软质量分 |
| 8 | 环境、Runner、权限、依赖或 Verifier 缺陷被记为**模型 0 分** |
| 9 | Solution、隐藏 Tests、答案或凭据泄漏，或 Agent 能篡改可信评分结果 |
| 10 | 环境不可恢复、运行有残留、结果不稳定或依赖旧产物 |
| 11 | 来源、License、隐私、授权或数据权属不清 |
| 12 | 重复题、表面变体题、冷门薄题，或与申报 Windows 能力实质不符 |
| 13 | 不满足模型区分度要求，整改后仍无有效区分 |
| 14 | 无法在约定时间和资源预算内稳定完成判分 |
| 15 | **未经甲方自检 PASS 即开跑**，或**跑分后修改题包内容**（导致 `task_checksum` 与交付包不符） |
| 16 | **验收侧交付包缺 `solution/reference/**` 或隐藏测试副本**（甲方无法独立复现验收；215/216 的实际退回理由之一） |
| 17 | 缺测、SKIP 或执行故障被写成 **FAIL 并输出正式 0 分**（应为 `INVALID`：写 `invalid.txt`、删除 `reward.txt`） |

---

## 二、Definition of Done（14 项）

单题**同时满足**以下条件才可申报最终验收：

| # | 条件 |
|---|---|
| 1 | 通过 Windows 价值反事实判定**与机制门禁 F1–F6**（`scripts/check_windows_mechanism.py` 退出码 `0`；题面含排他声明；包内无自我否认表述） |
| 2 | 是冻结 Schema 可直接加载运行的标准 Harbor Task |
| 3 | 题面清晰、实际下发，且不泄露实现 |
| 4 | 所有 required testcase 与题面/公开契约双向对应 |
| 5 | 核心测试验证真实功能和 Windows 机制，接受合理等价实现 |
| 6 | **no-change 独立 3 次均为 0**，P2P 均通过且核心 F2P 因目标缺陷失败 |
| 7 | **Golden 独立 3 次均为 1**，无 SKIP、MISSING、ERROR 或旧产物复用 |
| 8 | 正式评分无权重、无部分分、无 LLM/Agent Judge |
| 9 | Qwen3.8-Max-0902 与 Opus 5 各 3 次有效运行并满足**区分度**要求 |
| 10 | （可选）GLM-5.3 与 Kimi K3 若运行则无模型无关 infra/质量问题；**自 2026-10-13 起不再要求运行** |
| 11 | 干净重建或恢复、清理、回滚和残留检查通过 |
| 12 | 无 Solution、测试、答案、凭据和评分通道泄漏 |
| 13 | 来源、授权、污染、版本和变更记录完整 |
| 14 | 采购方最终复验通过并冻结版本 |

---

## 三、单题验收层级（11 层）

| 层级 | 必查内容 |
|---|---|
| 来源与合规 | Repo、Commit、License、授权、隐私、Lineage、污染和重复 |
| Windows 准入 | 反事实判定、目标 Windows Runtime、核心 Windows 机制是否位于成功路径 |
| Harbor 格式 | 标准目录、Schema、入口、版本、资源和超时可被平台直接加载 |
| 环境 | 可构建/恢复、依赖锁定、权限可控、清理无残留，E2–E4 不以 Mock 替代 |
| 题面与测试 | 要求真实下发、双向映射完整、无越界要求、功能验证且接受合理多解 |
| 对照 | no-change 3 次为 0，Golden 3 次为 1，干净重建/恢复成立 |
| 评分 | 无权重、无部分分、F2P/P2P 全过为 1 否则为 0，异常为 INVALID |
| 多模型 | Qwen/Opus 各 3 次满足区分度（GLM/Kimi 自 2026-10-13 起可选；若运行则不得有模型无关故障） |
| 安全与完整性 | Solution/隐藏 Tests 不可见；无网络取答案、本地搜答案、篡改测试/评分或旧产物复用 |
| 版本 | 题包、环境、测试、Solution、运行结果和整改记录可对应到同一冻结版本 |

---

## 四、逐运行状态与归因

### 状态取值

| 类别 | 取值 |
|---|---|
| testcase 状态 | `PASS` / `FAIL` / `SKIP` / `MISSING` / `ERROR` / `NOT_RUN` |
| 运行有效性 | `VALID` / `INVALID` / `PENDING` / `CANCELLED` |
| 质检结论 | `PASS` / `FAIL` / `FLAG` / `BLOCKED` / `N/A` |

### 归因原则

> 编译失败、超时、缺测试和解析错误**只是现象**，必须继续定位为：
> **题面、测试、环境/平台、聚合器、证据完整性、模型能力或 Hack** 等根因。

**只有题面清晰、测试公平、环境有效且证据完整时，才能归为模型能力失败。**

---

## 五、Hack 与答案泄漏审查

### 审查项

- 联网搜索、下载上游源码、PR、Commit、Patch 或答案
- 读取本地 Solution、Golden、隐藏 Tests、其他题目、Git 残留、缓存或历史制品
- 修改 Tests、Verifier、结果文件或环境以绕过判分
- 复用旧二进制、伪造 PASS、跳过测试或只打印成功

### 四层分级（报告必须区分）

| 层级 | 含义 |
|---|---|
| 1. 尝试 | 有意图但未成功 |
| 2. 成功访问 | 实际读取/下载到了 |
| 3. 实际使用 | 把内容用于作答 |
| 4. 已证明影响成绩 | 有证据表明影响了分数 |

> **关键词未命中不能证明绝对无 Hack；请求失败也不能误写为下载成功。**

---

## 六、跨目录身份与一致性门禁

**唯一验收身份 = `task_id + task_version + task_hash`**

必须满足：

- [ ] Harbor Task、平台配置、镜像 Digest、验收材料和模型运行均**显式引用同一身份**
- [ ] `task_id` 在文件名、`task.toml`、来源材料、平台配置和结果文件中**一致**
- [ ] **镜像标签不是不可变身份**，必须另存实际 **Digest**
- [ ] 无历史 ID 误用（如 D6-002 包内误用 D6-001 ID 类问题）——必须修正，**不得只在备注中长期兼容**
- [ ] 任何题面/环境/Solution/Tests/required testcase 变更均**升级题目版本**并重新执行受影响验收
- [ ] 批次自动校验**拒绝**：缺引用、错 ID、错版本、Hash 不匹配、同一题多真源

---

## 七、稳定性验收（第七章 7.4）

提交验收前至少完成：

- [ ] no-change 独立运行 **3 次**，结果均为 **0**
- [ ] Golden 独立运行 **3 次**，结果均为 **1**
- [ ] 至少一次从**干净环境重新构建或恢复**后复验
- [ ] 每次 required testcase 集合和终态一致，无**非模型原因**抖动
- [ ] 清理或快照恢复后**无影响后续运行的残留**

---

## 八、快速验收自检表

> **前四项必须在跑分之前完成**（阶段 4.5 硬门）；其余各项在跑分之后逐条核对。

```
[ ] ① 已预打包为交付 ZIP（此时尚未跑分）
[ ] ② 甲方 windows-harbor-qc 自检退出码 = 0（PASS）
[ ] ③ environment/adapter.toml 可被 TOML 解析（无扁平 key / 同名 [table] 冲突）
[ ] ④ 自检 PASS 后题包内容已冻结，跑分期间只新增 jobs/ 与 extras/
---- 以下为跑分后核对 ----
[ ] 反事实判定通过（附理由）
[ ] 标准 Harbor 五件套齐全，无自定义必需字段
[ ] instruction.md 不泄解法
[ ] environment/ 不泄 Solution / 隐藏测试
[ ] testcase ↔ 题面双向映射完整
[ ] 二值评分，无权重/部分分/LLM Judge
[ ] INVALID 与 0 分严格区分
[ ] Golden 3×1（无 SKIP/MISSING/ERROR/旧产物）
[ ] no-change 3×0（P2P 全过 + 核心 F2P 失败）
[ ] 至少 1 次干净重建复验
[ ] Qwen 3 次 + Opus 3 次，区分度满足
[ ] （可选）GLM/Kimi 若运行则有效；2026-10-13 起不强制
[ ] Hack 四层分级审查完成
[ ] 身份三元组全链一致
[ ] 镜像 Digest 已另存
[ ] delivery-extras 齐全
[ ] checksums.sha256 生成
[ ] Git 冻结版本可定位
```
