---
name: harbor-windows
description: >
  Windows 专项 Coding Bench（Harbor Windows）题包生产、交付与自动化模型验证全流程。按《Windows 专项 Coding Bench 数据采购》（windwos-第二版，替代 v1.0.2）
  生成符合冻结 Harbor Schema（默认 1.3）的标准题包，覆盖 Windows 价值反事实判定、标准 Harbor 五件套构题、F2P/P2P 二值判分、
  Golden/no-change 对照、Qwen3.8-Max-0902 / Opus 5 各 3 次 的自动化模型区分度验证（GLM-5.3 / Kimi K3 自 2026-10-13 起可选，不再必需）、身份三元组一致性与 delivery-extras 伴随材料交付。
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

## 四条不可妥协的底线

生产前先记住，任何情况下不得违反：

1. **Windows 价值**：换 Linux/macOS 后主要实现、错误根因、Evaluator 若基本不变 → 不是 Windows 专项题
2. **二值判分**：required F2P + P2P 全过 = 1，否则 = 0；异常 = INVALID（**不得伪装成 0 分**）。无权重、无部分分、无 LLM Judge
3. **身份唯一**：全包统一 `task_id + task_version + task_hash`；镜像 tag 不是身份，必须另存 Digest
4. **跑分前必须先过甲方自检**（2026-10-12 起，硬性前置门）：在真实 Windows Runtime 中开跑
   **任何**一轮（环境验证、Golden/no-change 对照、模型验证）之前，必须先对待交付形态的题包
   执行甲方 `windows-harbor-qc` 自检并达到退出码 `0`（PASS）。**自检未过就开跑 = 整批白跑**：
   待检缺陷全是静态可查的（TOML 能否解析、引用文件是否存在、文件命名、Task dirhash），
   而一轮完整验证要花 8 轮模型调用 + 6 轮对照。
   自检 PASS 后题包内容即**冻结**，任何后续改动（哪怕只改一个注释）都会改变 Harbor dirhash，
   使已跑出的 `task_checksum` 全部失效、必须全部重跑。
   → 详见「4.5 跑分前置门（硬性）」与 `references/06-acceptance-gates.md`

> 详细展开见 `references/01-spec-requirements.md` 与 `references/06-acceptance-gates.md`。

---

## 生产流程

```
0. 冻结基线
   → 1. 候选与 Windows 价值预筛
   → 2. 来源/授权/污染/重复检查
   → 3. 标准 Harbor 构题
   → 4. 题面与 testcase 双向审查
   → 4.5 🚦【硬性前置门】预打包 + 甲方 windows-harbor-qc 自检（不 PASS 禁止开始任何跑分）
   → 5. Windows 环境验证
   → 6. Golden / no-change / 反例验证
   → 7. 多模型验证（Qwen/Opus 各 3；GLM/Kimi 可选）
   → 8. Hack 与泄漏审查
   → 9. 身份与材料一致性校验
   → 10. 版本冻结与交付
```

> **4.5 是硬门，不是建议**。它必须在 5/6/7 之前完成，且 PASS 之后题包内容冻结。
> 顺序恒为：**定稿 → 预打包 → 自检 PASS → 冻结 → 跑分 → 组装 `jobs/` → 交付**。

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
| 精确模型标识 | 必需：`Qwen3.8-Max-0902`、`Opus 5`；可选：`GLM-5.3`、`Kimi K3`（2026-10-13 起） |

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
- **答案不上题面**：题面只写**现象 + 公开契约 + 验收标准**。必须给出的公开契约
  （API 名称与签名、错误 `kind` 取值表、异常类型）照常写；但**不得**写根因诊断，
  **不得**写出正确的常量/布局/字段/校验和变体，也**不得**给"先改哪、再改哪"的
  修复顺序 —— 这些必须由 Agent 从样本与运行结果自行推导

**初始态代码写法**（`environment/workspace/`）：
- **不得有引导性注释**：不得出现 `TODO` / `FIXME` / `XXX` / `HACK` / `BUG` 之类标记，
  也不得出现「这里不对」「应该改成…」「注意此处」「修复点」「待修复」之类指认；
  更不得用注释复述题面、标注被植入缺陷的位置或暗示正确实现与正确参数。
  注释只描述代码**当前**在做什么（也就是那些缺陷行为本身）
- 允许保留**中性的、与真实历史一致的**文档与注释（例如过时的草稿设计文档），
  但它们只能描述**曾经以为的样子**，不得反向给出正确布局或"照这个改"的指引
- 判断标准：缺陷必须靠**读样本 / 跑测试 / 读运行时错误**才能定位，不能靠注释直接指名

### 4. 题面与 testcase 双向审查

建立并核对双向映射：

```
题面要求/公开契约 → testcase → F2P/P2P 分组
testcase → 题面要求/公开契约 → 预期行为
```

逐条检查 7 项（越界要求、相反要求、事后契约、真实生产路径、验证功能而非写法、接受等价实现、P2P 相关性、F2P 因果性）
→ `references/04-testcase-mapping.md`

**产出**：`delivery-extras/tasks/<task-id>/testcase_mapping.csv`

### 4.5 🚦 跑分前置门（硬性）

**规则**：在真实 Windows Runtime 中开跑**任何**一轮之前（阶段 5 的环境验证、
阶段 6 的 Golden/no-change 对照、阶段 7 的模型验证），必须先对**待交付形态**的题包
执行甲方 `windows-harbor-qc` 自检，并达到退出码 `0`。
退出码 `1`（FAIL）或 `2`（BLOCKED）时**一律不得开始跑分** —— 先修包、再自检，直到 PASS。

**自检包位置**：`harbor-windows/_reference/windows-harbor-qc/`
（甲方最新版；2026-10-12 版共 34 个文件，可用包内 `MANIFEST.sha256` 自校。
甲方换版后按同一路径整体替换，并把旧版 `report.md` 归档到 `_qc_runs/`。）

**调用方式**（先预打包，再对 ZIP 自检）：

```powershell
$SKILL = "<skill目录>"
$QC    = "<仓库根>/harbor-windows/_reference/windows-harbor-qc"

# 1) 预打包（此时还没跑分，jobs/ 为空或仅含对照轮）
python "$SKILL/scripts/package_task_zip.py" `
    --task-dir <题包目录> --out-dir <出包目录> --verify

# 2) 甲方自检 —— 必须对 ZIP，而不是对源码目录：
#    只有 ZIP 形态才等价于甲方真正拿到的那份包
powershell -NoProfile -ExecutionPolicy Bypass `
    -File "$QC/scripts/run_delivery_qc.ps1" `
    -InputPath <出包目录>/<task_id>-v<版本>-delivery.zip `
    -OutPath   <出包目录>/qc-report

# 3) 只看退出码
#    0 = PASS      → 允许进入跑分
#    1 = FAIL      → 禁止跑分；按 qc-report/report.md 逐条修包后重跑本步骤
#    2 = BLOCKED   → 禁止跑分；先补齐十项人工复核证据
```

**必须 PASS 的静态门**（逐项见自检包内 `references/quality-gates.md`）：

| 门 | 检查内容 |
|---|---|
| 交付布局 | `environment/adapter.toml` **必须能被 TOML 解析器解析**；`environment/` 七个必备脚本齐全；ZIP 内层根目录名 = `<task_id>-v<版本>-delivery` |
| Harbor 静态 | 五件套齐全；`.ps1` / `.bat` 中被引用的路径**必须真实存在**；无自定义必需字段；无 Solution / 隐藏 Tests 泄漏 |
| jobs 结构 | 每个 job 含 `config.json` + `lock.json` + `result.json` + `trial.log` + `artifacts/manifest.json` + `verifier/{result.json,reward.txt,test-stdout.txt,verifier.log}`；模型轮另有 `agent/model-result.json` + `agent/trajectory.jsonl`；Oracle 轮另有 `agent/oracle.txt` + `agent/qc-oracle-application.json` |
| 判分证据 | `verifier/result.json` 的有效性、二值分数与 testcase 集合必须被自检脚本认可；`tests/required_testcases.json` 存在，且与各 job 的 testcase 集合**逐字一致**（以 `report.md` 报错为准，不要凭记忆自拟协议） |
| 身份 | 全部 job 的 `task_checksum` 与交付包的 **Harbor dirhash 完全一致** |

> ⚠️ **已知差异（2026-10-13 起）：`task.toml` 不得写 `docker_image`**。
> 基础镜像只由 `environment/Dockerfile` 的 `FROM` 声明并 pin 到不可变 digest。
> 甲方 QC 的 `run_qc.py` 仍把该字段当作必需项，缺失会写 `task.toml has no docker_image`
> 并把「静态结构」判为 FAIL、退出码 `1` —— **这正是预期行为**，不要为过检查把字段写回去；
> 正确做法是在交付说明里记录该差异（详见 `references/06-acceptance-gates.md` 零节）。
> 两个配套坑：`run_qc.py` 的 `--attempts` 最小为 `3`（传 `1`/`2` 会在 argparse
> 阶段直接退出，日志里只剩一句 usage，极易误判成容器起不来）；**Harbor 侧不受影响** ——
> `harbor/environments/definition.py` 的 `should_use_prebuilt_docker_image()` 在
> `docker_image` 为空时返回 `False`，于是自动回落到 `environment/Dockerfile` 构建，
> `--force-build` 只是排除缓存的额外保险。

> ⚠️ **`adapter.toml` 的经典坑**：甲方 `inspect_delivery.py` 读的是**扁平 key**
> （`prepare` / `validate` / `run` / `restore` / `cleanup` / `workspace`）。
> 若同一文件里又写了同名的 `[prepare]` / `[validate]` / `[test]` / `[restore]` /
> `[cleanup]` / `[exec_agent]` 表，TOML 会直接解析失败
> （`Cannot overwrite a value (at line N, column M)`）。
> **扁平 key 必须保留，冲突的表名必须改掉。**

**第二条铁律：跑分对象必须与最终交付包同一份内容。**
Harbor dirhash 覆盖除顶层 `jobs/` 以外的全部文件，因此：

- ✅ 跑分**之后**组装 `jobs/` 是安全的 —— 它不影响 checksum
- ❌ 跑分**之后**再动 `task.toml` / `instruction.md` / `environment/` / `solution/` /
  `tests/` / `verifier/` 的任何字节，都会使全部 `task_checksum` 失效，**必须整批重跑**

**与人工复核的关系**：十项人工复核（`quality-review.json`，见自检包内
`references/manual-review.md`）与自动静态门**相互独立**；自动门全绿也只是
`BLOCKED` 可解除的前提之一，人工项必须逐条留证。

> **代价对比（为什么定成硬门）**：218 号包在**旧版内容**上跑满 14 轮（8 轮模型 + 6 轮对照）
> 之后，甲方自检依然 FAIL：`adapter.toml` 第 38 行 TOML 非法、`solution/reference/wlogseg`
> 与 `tests/test_wlogseg_semantics.py` 被脚本引用却不存在、job 缺 `lock.json` /
> `verifier/verifier.log` / `artifacts/manifest.json`，且 `task_checksum` 与交付包不一致。
> 这些**全部**在跑第一轮之前就能查出来。215 v2.1.0 与 216 v1.2.0 也已带着同一个
> `adapter.toml` 缺陷交付甲方。**先自检，再花钱。**

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
| **Qwen3.8-Max-0902** | 各 3 次 | 主要难度模型（**必需**） |
| **Opus 5** | 各 3 次 | 主要难度模型（**必需**） |
| GLM-5.3 | 可选 | 额外可运行性佐证；**自 2026-10-13 起不再必需** |
| Kimi K3 | 可选 | 额外可运行性佐证；**自 2026-10-13 起不再必需** |

> **规则变更（2026-10-13）**：甲方确认 GLM-5.3 与 Kimi K3 **不再是交付必需项**。
> 新生产的题包只跑 控制组（no-change ×3 / Golden ×3）+ Qwen3.8-Max-0902 ×3 + Opus 5 ×3，
> 合计 12 轮；已有 GLM/Kimi 结果的旧题包**不回退、不改写**，仍按其当时口径归档。

**区分度准入（满足任一）**：
1. `Opus5.model_score_sum > Qwen.model_score_sum`；或
2. 两者 `model_score_sum` 相等，且 `Opus5.testcase_pass_sum > Qwen.testcase_pass_sum`

条件 2 **不限于「双方均为 0」**：Qwen 三轮全满分（3 = 3）时同样走条件 2。
此时正式分已顶格、拉不开差距，区分度全部由 `testcase_pass_sum` 承担，
**Opus 必须严格多出**才算通过。因此「Qwen 全满分」本身不再是出局理由，
但 required testcase 的条数与颗粒度必须真的能分开两者。

不满足 → 整改或替换。只统计 **VALID** 运行；INVALID 必须查明原因并补跑。

**自动化执行**（一条命令跑完 4 个模型并算区分度）：

```bash
# 1) 填凭据（推荐环境变量，避免明文入库）
export HARBOR_WINDOWS_ALIYUN_KEY=<aliyun key>   # qwen / glm / kimi 共用
export HARBOR_WINDOWS_BLVR_KEY=<blvr key>       # opus

# 2) 全量验证（Qwen 3 + Opus 3；GLM/Kimi 自 2026-10-13 起可选）
python scripts/run_model_validation.py \
    --tasks outside_harbor-assets --out delivery-extras/tasks

# 3) 平台 harness 跑完 F2P/P2P 并回填 report.json 分数后，只算区分度
python scripts/run_model_validation.py --score-only --out delivery-extras/tasks
```

前提：`pip install httpx`。端点与模型名的唯一来源是仓库根 `models.local.json`（脚本从自身位置逐级上溯自动定位）。

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
- 打交付 ZIP：`scripts/package_task_zip.py`（**必须含 `solution/`、`source.json`、`jobs/`**；仅排除 `extras/` 与缓存，缺必备件即拒发）；
  输出 ZIP 名与内层根目录名均为 `<task_id>-v<题目版本>-delivery`（`task_id` 取自 `task.toml` 的
  `[metadata].task_id`，**不得**用本地目录名派生），解压到 `harbor-windows/` 后与飞书附件名逐字一致
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

### 飞书交付包 ↔ 本地目录严格对应（强制）

**本地题包目录名 = 飞书交付附件名去 `.zip`**，即带版本号与 `-delivery` 后缀的完整名字；
解压即得正确目录，禁止手工改名：

```text
wfflab__wchunk-216-v1.2.0-delivery/    # ← wfflab__wchunk-216-v1.2.0-delivery.zip
wfflab__wfmt-215-v2.1.0-delivery/      # ← wfflab__wfmt-215-v2.1.0-delivery.zip
├── environment/  jobs/  solution/  tests/  verifier/
├── instruction.md
└── task.toml
```

| # | 硬性要求 |
|---|---|
| 1 | 目录名逐字照抄附件名（去 `.zip`），**保留版本号与 `-delivery` 后缀** |
| 2 | **禁止**用 `task_id`（如 `wfflab__wchunk-216`）当目录名：它不含版本，无法区分 v1.1.0 / v1.2.0 |
| 3 | 拉取方式固定为「下载交付附件 zip → 解压到 `harbor-windows/`」，解压出的顶层目录就是唯一合法落点 |
| 4 | 题包换版时目录名随之更换（`...-v1.2.0-delivery`），`harbor-windows/` 下**不得**留存旧版本目录 |
| 5 | `task_id` / `task_version` / `task_hash` / 镜像 Digest 仍以包内 `task.toml` 与 `_index/` 为准，不因目录名改写 |

> **一致性核对只认 `作业压缩包` 字段（2026-10-12 核定）**：飞书该表另有 `zhang质检`、
> `分数截图`、`oracle/nop截图` 等附件字段，它们是**过程证据**，不属于题包交付内容，
> **不参与**「本地与飞书一致」的判定。核对只比对 `作业压缩包` 字段的附件名（去 `.zip`）与
> `harbor-windows/` 下的题包目录名。

> 交付包**内部**结构以新版（v1.2.0 / v2.1.0）平铺式为准：顶层直接是
> `environment/ jobs/ solution/ tests/ verifier/ instruction.md task.toml`；
> 上方「题包本体 / 伴随材料」的 `outside_harbor-assets/` 嵌套式属旧版（≤ v1.1.0）历史形态。

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
| 12 | **先跑分、后自检**（或拖到交付前才自检） | 阶段 4.5 是硬性前置门：预打包 → 甲方 `windows-harbor-qc` 自检 PASS → 内容冻结 → 才允许跑任何一轮。跑完再改包 = 全部 `task_checksum` 失效，整批重跑 |
| 13 | `adapter.toml` 同时写扁平 key 与同名 `[table]` | 甲方读扁平 key；同名表会让 TOML 直接解析失败。**保留扁平 key，改掉冲突的表名** |

---

## 15 条一票否决（速查）

反事实不通过 / 题面不可解 / Golden≠1 或 no-change≠0 / P2P 在 base 失败或 F2P 无关 /
testcase 与题面冲突 / 靠字符串正则 Diff 判定 / 用权重部分分或 LLM Judge /
环境缺陷记 0 分 / Solution 或答案泄漏 / 环境不可恢复 / 来源授权不清 /
重复或表面变体题 / 区分度不足 / 无法在预算内判分 /
**未过甲方自检即开跑，或跑分后改包致 `task_checksum` 失效**

> 完整定义 → `references/06-acceptance-gates.md`

---

## 参考文件索引

| 文件 | 内容 |
|---|---|
| `references/01-spec-requirements.md` | 规范原文要求（采购目标、五大原则、题目要求） |
| `<仓库根>/harbor-windows/_reference/windows-harbor-qc/` | **甲方交付自检包（阶段 4.5 硬性前置门）**：`scripts/run_delivery_qc.ps1` 对交付 ZIP 执行交付布局门 + Harbor 静态门 + jobs 门 + 人工复核门；退出码 `0`=PASS / `1`=FAIL / `2`=BLOCKED；结论落在 `report.md` / `report.json` / `harbor/` |
| `references/02-windows-value.md` | Windows 价值反事实判定 + 12 方向 + 误判案例 |
| `references/03-harbor-task.md` | 标准 Harbor 结构、task.toml 字段、Windows 镜像要求 |
| `references/04-testcase-mapping.md` | 题面↔testcase 双向映射 + F2P/P2P 规范 |
| `references/05-delivery-structure.md` | 交付目录树 + delivery-extras 字段 |
| `references/06-acceptance-gates.md` | 一票否决 + DoD + 验收层级 |
| `references/07-legacy-conversion.md` | 旧 6 题转换的 12 项重做 + 变更对比 |
| `references/08-model-validation.md` | 多模型跑分自检：端点/命令/权限、QWEN thinking（§7.10）、计划任务绝对路径（§7.11）、**传输层超时（§7.12）**、网关非流式硬墙（§7.13）、**流式是正解（§7.14）** |
| `references/09-gz-package-analysis.md` | 压缩包结构分析 |
| `references/10-windows-ops-pitfalls.md` | Windows 题运维坑：容器适配 6 坑、计划任务编排 3 坑、飞书写回编码坑、`runner.py` 参数化与并行 |
| `references/11-latest-qc-requirements.md` | **最新质检要求（20261012 批次）**：魔法阈值禁令、无效槽位单列、Windows 价值映射与归类、权重废止、配置可解析、公开/隐藏分层与负访问证明 |
| `references/08-model-validation.md` | 多模型门槛、区分度计算、稳定性验收 |
| `references/09-gz-package-analysis.md` | 对 `Windows_SWE_d70d30df` 27 题现包的实测分析 |
| `scripts/validate_package.py` | 题包结构与身份一致性校验（实测 27 题包可用） |
| `scripts/build_delivery_extras.py` | 批量生成 delivery-extras 骨架 |
| `scripts/build_jobs.py` | **由资格汇总生成 `jobs/<job-id>/{agent,verifier}`**（故障轮保留并标 `excluded`；含凭据扫描） |
| `scripts/build_required_testcases.py` | **生成甲方 QC 必备的 `tests/required_testcases.json`**（F2P/P2P 依据取自 candidate/golden 对照或 `swelive_spec.json`） |
| `scripts/align_report_protocol.py` | **对齐甲方 QC 报告协议 aggregate-v1**：rubric `test_ids` 加 `f2p-`/`p2p-` 前缀、重建清单、同步 `judge.toml` 的 `source_sha256` |
| `scripts/package_task_zip.py` | **打交付 ZIP**：含 `solution/`、`source.json`、`tests/`、`jobs/`；仅排除 `extras/` 与缓存；ZIP 名 = `<task_id>-v<版本>-delivery`，缺必备件即拒发 |
| `scripts/hash_package.py` | 身份三元组 `task_hash` 的计算与四处回写（公式只含 instruction / test_patch / oracle_patch / Dockerfile） |
| `scripts/run_model_validation.py` | **4 模型自动化验证 + 区分度准入计算** |
| 仓库根 `models.local.json` | 模型端点与凭据的**唯一来源**（脚本自动上溯定位；含明文凭据，按甲方要求纳入版本控制） |
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

# 3) 多模型自动化验证（Qwen 3 + Opus 3；GLM/Kimi 自 2026-10-13 起可选）
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
