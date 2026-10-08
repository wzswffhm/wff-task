---
name: harbor-windows
description: >
  Windows 专项 Coding Bench（Harbor Windows）题包生产、交付与自动化模型验证全流程。按《Windows 专项 Coding Bench 数据采购》（windwos-第二版，替代 v1.0.2）
  生成符合冻结 Harbor Schema（默认 1.3）的标准题包，覆盖 Windows 价值反事实判定、标准 Harbor 五件套构题、F2P/P2P 二值判分、
  Golden/no-change 对照、Qwen3.8-Max-0902 / Opus 5 各 3 次 + GLM-5.3 / Kimi K3 各 ≥1 次的自动化模型区分度验证、身份三元组一致性与 delivery-extras 伴随材料交付。
  Use when the user asks to 出题/产题/构题/生产题包/交付题包 for Windows coding benchmark, mentions
  Windows 专项 Coding Bench、Harbor Windows、Harbor Task、Harbor 题包、SWE-bench-Live、swelive_spec、F2P/P2P、Golden 验证、
  no-change、模型区分度、多模型验证, or wants to convert/整改旧题包到本规范。Also use when reviewing whether an existing
  Windows 题包 meets the 验收标准, or when building delivery-extras 伴随交付材料.
  Keywords: Harbor Windows, harbor-windows, Windows bench, Harbor schema 1.3, task.toml, instruction.md, environment, solution, tests,
  test_patch, oracle patch, task_id + task_version + task_hash, ExternalImages, 脱敏, 供应商交付, model_runs 自动化验证.
---

# Windows 专项 Coding Bench 题包生产

按《Windows 专项 Coding Bench 数据采购》（`windwos-第二版`）生产**标准 Harbor Task** 并完成交付。
本 skill 是**生产流程的执行入口**；详细规则按需查阅 `references/`。

## 适用范围

| 场景 | 入口 |
|---|---|
| 从零生产新题包 | 本文件「生产流程」章节 |
| 整改/转换旧题包 | `references/07-legacy-conversion.md` |
| 检查题包是否达标 | `references/06-acceptance-gates.md` + `scripts/validate_package.py` |
| 构建 delivery-extras 伴随材料 | `references/05-delivery-structure.md` |
| 理解某条规则的原文依据 | `references/01-spec-requirements.md` |

## 三条不可妥协的底线

生产前先记住，任何情况下不得违反：

1. **Windows 价值**：换 Linux/macOS 后主要实现、错误根因、Evaluator 若基本不变 → 不是 Windows 专项题
2. **二值判分**：required F2P + P2P 全过 = 1，否则 = 0；异常 = INVALID（**不得伪装成 0 分**）。无权重、无部分分、无 LLM Judge
3. **身份唯一**：全包统一 `task_id + task_version + task_hash`；镜像 tag 不是身份，必须另存 Digest

> 详细展开见 `references/01-spec-requirements.md` 与 `references/06-acceptance-gates.md`。

---

## 生产流程

```
0. 冻结基线
   → 1. 候选与 Windows 价值预筛
   → 2. 来源/授权/污染/重复检查
   → 3. 标准 Harbor 构题
   → 4. 题面与 testcase 双向审查
   → 5. Windows 环境验证
   → 6. Golden / no-change / 反例验证
   → 7. 多模型验证（Qwen/Opus 各 3 + GLM/Kimi 各 ≥1）
   → 8. Hack 与泄漏审查
   → 9. 身份与材料一致性校验
   → 10. 版本冻结与交付
```

### 0. 冻结基线

生产开始前**一次性冻结**并记录到 `delivery-extras/`：

| 冻结项 | 说明 |
|---|---|
| Harbor Schema 版本 | 默认 **1.3**；平台若确认升级，以书面冻结版为准 |
| Harness 版本 | 如 `harbor-rewardkit==0.1.7` |
| Windows 镜像/快照 | 含 base image 与 task image |
| 工具权限 / 网络策略 | 是否 air-gapped、allowlist |
| Token / 时间预算 | 与 `task.toml` 的 timeout 一致 |
| 采样参数 | temperature/top_p 等 |
| 精确模型标识 | `Qwen3.8-Max-0902`、`Opus 5`、`GLM-5.3`、`Kimi K3` |

> **模型或平台版本变更后，不得与旧结果直接比较；需要用于准入时应统一回刷。**

### 1. 候选与 Windows 价值预筛

对每个候选逐题回答**反事实问题**：

> 将目标 OS 替换为 Linux 或 macOS，主要实现、错误根因和 Evaluator 是否基本不变？

- 答案为「是」→ 淘汰或重新立意
- 判据、12 个主流方向、6 个常见误判 → `references/02-windows-value.md`

**产出**：`delivery-extras/tasks/<task-id>/metadata/labels.json`（主方向 + 次级标签 + 语言 + 任务类型 + 目标 Windows 环境 + 难度）

### 2. 来源/授权/污染/重复检查

每题建档，写入 `metadata/source_and_license.json` 与 `metadata/lineage_and_contamination.json`：

- Repo、Commit、Issue/PR、License、授权、隐私
- Lineage（是否衍生自其他题）、污染风险（是否与训练集重叠）
- 重复风险（是否与其他题实质相同或仅表面变体）

> 模板见 `assets/metadata-templates/`。

### 3. 标准 Harbor 构题

**固定结构**（不得新增自定义必需目录或私有字段）：

```
<task-id>/
├── task.toml          # 身份、版本、资源、超时、环境、入口
├── instruction.md     # Agent 唯一题面，不泄解法
├── environment/       # 可复现初始态 + Dockerfile；依赖锁定；不泄 Solution/隐藏 Tests
├── solution/          # 参考解/补丁，仅用于 Golden 验证
└── tests/             # 独立程序化 Verifier（F2P + P2P）
```

各部分职责、字段规范、Windows 镜像要求 → `references/03-harbor-task.md`
可直接复用的骨架 → `assets/harbor-skeleton/`

**题面写法**：
- **要写**：背景/现象、目标、功能边界、约束、允许修改范围、用户可见验收标准
- **不得写**：Golden Patch、答案路径、隐藏测试、精确修改位置、可照抄的实现步骤

### 4. 题面与 testcase 双向审查

建立并核对双向映射：

```
题面要求/公开契约 → testcase → F2P/P2P 分组
testcase → 题面要求/公开契约 → 预期行为
```

逐条检查 7 项（越界要求、相反要求、事后契约、真实生产路径、验证功能而非写法、接受等价实现、P2P 相关性、F2P 因果性）
→ `references/04-testcase-mapping.md`

**产出**：`delivery-extras/tasks/<task-id>/testcase_mapping.csv`

### 5. Windows 环境验证

- 真实 **Windows Runtime** 触发验证，**不得**用 Linux Mock / 普通容器替代
- 依赖版本锁定、**断网可复现**
- 权限可控、可清理、可恢复
- 每次运行前清除旧构建产物与系统残留

### 6. Golden / no-change / 反例验证

| 对照 | 干净环境要求 |
|---|---|
| **Golden** | 所有 required F2P+P2P 执行且 PASS；正式分 **1**；无 SKIP/MISSING/ERROR/旧产物复用；身份可核对 |
| **no-change** | P2P 全过；**至少一个核心 F2P 因目标缺陷失败**；正式分 **0**；失败原因非基础设施问题 |

- 两者必须使用**同一** base/环境/依赖/测试树/评分规则/资源预算
- **稳定性**：no-change 独立 **3 次全 0**；Golden 独立 **3 次全 1**；至少 1 次干净重建/恢复后复验
- **反例**：空实现、固定返回、提前退出、硬编码、只修一半、吞异常、禁用功能

> Golden 与题面冲突时，**修题目/测试/参考解，不得改题意凑 Golden=1**。
> 证据归档 → `delivery-extras/tasks/<task-id>/evidence/{golden,no_change,clean_room,negative_and_equivalent_controls,cleanup_and_restore}/`

### 7. 多模型验证

| 模型 | 次数 | 用途 |
|---|---|---|
| **Qwen3.8-Max-0902** | 各 3 次 | 主要难度模型 |
| **Opus 5** | 各 3 次 | 主要难度模型 |
| GLM-5.3 | ≥1 次 | 可运行性 + 基础质量 |
| Kimi K3 | ≥1 次 | 可运行性 + 基础质量 |

**区分度准入（满足任一）**：
1. `Opus5.model_score_sum > Qwen.model_score_sum`；或
2. 两者 `model_score_sum = 0` 且 `Opus5.testcase_pass_sum > Qwen.testcase_pass_sum`

不满足 → 整改或替换。只统计 **VALID** 运行；INVALID 必须查明原因并补跑。

**自动化执行**（一条命令跑完 4 个模型并算区分度）：

```bash
# 1) 填凭据（推荐环境变量，避免明文入库）
export HARBOR_WINDOWS_ALIYUN_KEY=<aliyun key>   # qwen / glm / kimi 共用
export HARBOR_WINDOWS_BLVR_KEY=<blvr key>       # opus

# 2) 全量验证（Qwen 3 + Opus 3 + GLM 1 + Kimi 1）
python scripts/run_model_validation.py \
    --tasks outside_harbor-assets --out delivery-extras/tasks

# 3) 平台 harness 跑完 F2P/P2P 并回填 report.json 分数后，只算区分度
python scripts/run_model_validation.py --score-only --out delivery-extras/tasks
```

前提：`pip install httpx`。端点与模型名见 `scripts/model_endpoints.template.json`。

> **⚠️ 分工边界**：该脚本是**模型调用与记录层**，只负责发起调用、保存轨迹与补丁、
> 区分 VALID/INVALID、计算区分度；**不负责**在真实 Windows Runtime 中执行 F2P/P2P。
> 因此 `per_testcase.json` 初值为 `NOT_RUN`、`report.json.score` 初值为 `null`，
> **正式分必须由平台 harness（`test.ps1` + `grade.py`）执行后回填**，再跑 `--score-only`。
> 这条分工是为守住"不得用 Linux Mock 替代真实 Windows Runtime 验证"的红线。

> **模型门槛不能覆盖数据质量门槛**，不得为造分差增加未声明要求或冷门陷阱。
> 运行记录 → `delivery-extras/tasks/<task-id>/model_runs/<model>/`

### 8. Hack 与泄漏审查

审查 Agent 是否：联网搜答案/下载上游 Patch、读本地 Solution/Golden/隐藏 Tests/Git 残留/缓存、
改 Tests/Verifier/结果文件绕过判分、复用旧二进制/伪造 PASS。

> 报告须区分**尝试 / 成功访问 / 实际使用 / 已证明影响成绩** 四层。
> 关键词未命中 ≠ 绝对无 Hack；请求失败 ≠ 下载成功。

### 9. 身份与材料一致性校验

运行校验脚本：

```bash
python scripts/validate_package.py --package <题包根目录> --schema-version 1.3
```

检查项：身份三元组一致、目录结构合规、无自定义必需字段、无 Solution/隐藏 Tests 泄漏、
伴随材料齐全、Hash 匹配。详见 `references/06-acceptance-gates.md`。

### 10. 版本冻结与交付

- Git Tag/Release + 环境 Digest + 批次清单**可相互定位**
- **Git 冻结版本为唯一来源**（不再以聊天附件/多个压缩包作为主版本传递）
- 生成 `checksums.sha256`
- 由资格汇总生成 `jobs/`：`scripts/build_jobs.py`（每次跑分一个 `<job-id>/{agent,verifier}`）
- 生成甲方 QC 必备的 `tests/required_testcases.json`：`scripts/build_required_testcases.py`
- 对齐甲方 QC 报告协议 aggregate-v1（rubric `test_ids` 需 `f2p-`/`p2p-` 前缀）：`scripts/align_report_protocol.py`
- 打交付 ZIP：`scripts/package_task_zip.py`（**必须含 `solution/`、`source.json`、`jobs/`**；仅排除 `extras/` 与缓存，缺必备件即拒发）
- 交付结构见 `references/05-delivery-structure.md`

---

## 交付物清单

**题包本体**（每题）：

```
outside_harbor-assets/<task-id>/
├── task.toml
├── instruction.md
├── environment/
├── solution/
└── tests/
```

**平台导入**（每题）：`outside_harbor/<task-id>.json`
（仅用于平台导入，**不等于**标准 Harbor Task；须与题包本体绑定同一身份三元组）

**作业记录**（`outside_harbor-assets/jobs/`，与 `<task-id>/` **平级**）：
每次跑分一个 `<job-id>/`，内含 `agent/`（模型侧）+ `verifier/`（判分侧）；
作业 ID = runner 的 `run_id`，与资格汇总一一对应。由 `scripts/build_jobs.py` 生成。
仓库内先落 `<task-id>/jobs/`（一题一目录），组装批次包时平级上移。

**伴随材料**（`delivery-extras/`，**缺则不得验收**）：
批次级汇总文件 + `tasks/<task-id>/` 下的 metadata / evidence / model_runs / testcase_mapping / quality_review / remediation

> 完整目录树与字段说明 → `references/05-delivery-structure.md`

---

## 常见陷阱（生产中最易踩）

| # | 陷阱 | 正确做法 |
|---|---|---|
| 1 | 只交 Harbor 题包，忘了伴随材料 | 「题包只含标准 Harbor」≠ 只交题包；**缺伴随材料不得验收** |
| 2 | 题面写 PowerShell/盘符就以为有 Windows 价值 | 看**核错机制**是否依赖 Windows，不是看表象 |
| 3 | 把 INVALID 记成模型 0 分 | INVALID 必须查明补跑，**不得纳入难度统计** |
| 4 | 沿用历史 `judge.toml`/`rubric.json` 权重 | 改为 required F2P/P2P 二值；兼容文件只能表达二值 |
| 5 | 用镜像 tag 当身份 | 另存**不可变 Digest** |
| 6 | 环境缺陷被大 try/catch 吞成模型 0 分 | 基础设施异常必须与候选功能失败**分开** |
| 7 | 异步/负观察只看退出码 | 必须有**完成回执或独立健康哨兵** |
| 8 | 测试绑定 Golden 私有函数名/调用顺序 | 只验公共契约与可观察行为，接受等价实现 |
| 9 | 大文件全挪出题包 | 离线依赖/fixture 保留在 `environment/` 或 `tests/` 允许位置，保离线可复现 |
| 10 | `.ap-tools` 或含 Oracle 的 `harbor/` 进 Agent 可见环境 | 两者均**不得进入** Agent 可见环境或评测镜像 |
| 11 | 交付 ZIP 缺 `jobs/`，或把上游故障轮记成 0 分 | `jobs/<job-id>/{agent,verifier}` 必须齐全；故障轮标 `excluded` 并写明原因；原始轨迹未留存时**显式声明缺口，不得伪造** |

---

## 14 条一票否决（速查）

反事实不通过 / 题面不可解 / Golden≠1 或 no-change≠0 / P2P 在 base 失败或 F2P 无关 /
testcase 与题面冲突 / 靠字符串正则 Diff 判定 / 用权重部分分或 LLM Judge /
环境缺陷记 0 分 / Solution 或答案泄漏 / 环境不可恢复 / 来源授权不清 /
重复或表面变体题 / 区分度不足 / 无法在预算内判分

> 完整定义 → `references/06-acceptance-gates.md`

---

## 参考文件索引

| 文件 | 内容 |
|---|---|
| `references/01-spec-requirements.md` | 规范原文要求（采购目标、五大原则、题目要求） |
| `references/02-windows-value.md` | Windows 价值反事实判定 + 12 方向 + 误判案例 |
| `references/03-harbor-task.md` | 标准 Harbor 结构、task.toml 字段、Windows 镜像要求 |
| `references/04-testcase-mapping.md` | 题面↔testcase 双向映射 + F2P/P2P 规范 |
| `references/05-delivery-structure.md` | 交付目录树 + delivery-extras 字段 |
| `references/06-acceptance-gates.md` | 一票否决 + DoD + 验收层级 |
| `references/07-legacy-conversion.md` | 旧 6 题转换的 12 项重做 + 变更对比 |
| `references/08-model-validation.md` | 多模型跑分自检：端点/命令/权限、QWEN thinking（§7.10）、计划任务绝对路径（§7.11）、**传输层超时（§7.12）**、网关非流式硬墙（§7.13）、**流式是正解（§7.14）** |
| `references/09-gz-package-analysis.md` | 压缩包结构分析 |
| `references/10-windows-ops-pitfalls.md` | Windows 题运维坑：容器适配 6 坑、计划任务编排 3 坑、飞书写回编码坑、`runner.py` 参数化与并行 |
| `references/08-model-validation.md` | 多模型门槛、区分度计算、稳定性验收 |
| `references/09-gz-package-analysis.md` | 对 `Windows_SWE_d70d30df` 27 题现包的实测分析 |
| `scripts/validate_package.py` | 题包结构与身份一致性校验（实测 27 题包可用） |
| `scripts/build_delivery_extras.py` | 批量生成 delivery-extras 骨架 |
| `scripts/build_jobs.py` | **由资格汇总生成 `jobs/<job-id>/{agent,verifier}`**（故障轮保留并标 `excluded`；含凭据扫描） |
| `scripts/build_required_testcases.py` | **生成甲方 QC 必备的 `tests/required_testcases.json`**（F2P/P2P 依据取自 candidate/golden 对照或 `swelive_spec.json`） |
| `scripts/align_report_protocol.py` | **对齐甲方 QC 报告协议 aggregate-v1**：rubric `test_ids` 加 `f2p-`/`p2p-` 前缀、重建清单、同步 `judge.toml` 的 `source_sha256` |
| `scripts/package_task_zip.py` | **打交付 ZIP**：含 `solution/`、`source.json`、`tests/`、`jobs/`；仅排除 `extras/` 与缓存，缺必备件即拒发 |
| `scripts/hash_package.py` | 身份三元组 `task_hash` 的计算与四处回写（公式只含 instruction / test_patch / oracle_patch / Dockerfile） |
| `scripts/run_model_validation.py` | **4 模型自动化验证 + 区分度准入计算** |
| `scripts/model_endpoints.template.json` | 模型端点与凭据配置模板 |
| `scripts/README.md` | 六个脚本的完整用法说明 |
| `assets/harbor-skeleton/` | 标准 Harbor 五件套骨架（含可直接复用的 grade.py / test.ps1 / Dockerfile） |
| `assets/metadata-templates/` | 伴随材料 JSON 模板（source_and_license / labels / lineage / manifest） |

## 快速上手（六条命令）

```bash
SKILL=<skill目录>

# 0) 依赖（多模型验证需要 httpx）
pip install httpx

# 1) 从骨架起一题（按该 README 的 cp 清单操作）
cat "$SKILL/assets/harbor-skeleton/README.md"

# 2) 批量生成伴随材料骨架
python "$SKILL/scripts/build_delivery_extras.py" \
    --assets outside_harbor-assets --out delivery-extras

# 3) 多模型自动化验证（Qwen 3 + Opus 3 + GLM 1 + Kimi 1）
export HARBOR_WINDOWS_ALIYUN_KEY=<key>
export HARBOR_WINDOWS_BLVR_KEY=<key>
python "$SKILL/scripts/run_model_validation.py" \
    --tasks outside_harbor-assets --out delivery-extras/tasks

# 4) 出包前校验（PASS/FAIL/FLAG）
python "$SKILL/scripts/validate_package.py" \
    --package <题包根目录> --schema-version 1.3 --json validate-report.json

# 5) 由资格汇总生成 jobs/（每次跑分一个 job；故障轮保留并标 excluded）
python "$SKILL/scripts/build_jobs.py" \
    --task-dir <题包目录> --summary <model_runs_summary_*.json>

# 6) 打交付 ZIP（含 jobs/，自动排除 solution/ 与凭据），并逐文件核对
python "$SKILL/scripts/package_task_zip.py" \
    --task-dir <题包目录> --out-dir <出包目录> --verify
```

> 校验退出码：`0` 全过（可能含 FLAG）／`1` 存在 FAIL（不满足验收）／`2` 参数错误。
> 模型验证退出码：`0` 无明确失败／`1` 存在 INVALID 或区分度不通过。
> `build_jobs.py` 命中疑似凭据 exit=2；`package_task_zip.py` 检出禁入内容或核对不符 exit=2。
