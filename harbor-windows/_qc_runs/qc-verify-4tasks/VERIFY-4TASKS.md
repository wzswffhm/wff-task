# 215 / 216 / 218 / 219 四题质检符合性验证

验证时间：2026-10-14（本机 Windows / Python 3.13.15）
验证对象：

- `harbor-windows/wfflab__wfmt-215-v2.1.0-delivery`（包内身份 **2.1.1**）
- `harbor-windows/wfflab__wchunk-216-v1.2.0-delivery`（包内身份 **1.2.1**）
- `harbor-windows/wfflab__wlogseg-218-v1.1.0-delivery`（1.1.0）
- `harbor-windows/wfflab__wpeimg-219-v1.4.0-delivery`（1.4.0）

## 0. 判据来源

甲方最新质检包 `C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\`
只含报告与手册，不含可执行检查器。其手册 `evidence/manual/*.md` 与工作区
`harbor-windows/_reference/windows-harbor-qc/references/windows-procurement-qc-manual-20260927/`
6 个文件 **SHA-256 逐一相同**，故以该参考包内的检查器为判据执行。

本项目用到**三套**甲方检查器，检查范围不同，必须同时看：

| # | 检查器 | 检查内容 | 依据 |
|---|---|---|---|
| A | `run_qc.py::static_check()` | 15 类静态结构 + **脚本内引用路径存在性** + 泄漏检查 | 甲方自检包主入口 |
| B | `inspect_delivery.py::inspect_delivery()` | 交付层 6 类结构 + 身份字段 | 甲方交付层检查 |
| C | `validate_model_jobs.py::validate_jobs()` | job 归档层：缺件、alias 识别、`task_checksum` 一致、testcase 终态、Oracle/NOP 规则、轮次数量、凭据扫描 | 甲方 job 层校验 |

另有本项目自检与门禁：

| # | 判据 | 来源 |
|---|---|---|
| D | 本机静态 + 隔离（10 组） | `logs/local_checks.py` |
| E | 身份门：全部 job 的 `task_checksum` = 交付包 Harbor dirhash | `references/06-acceptance-gates.md` §0 |
| F | 区分度门禁（主模型 Opus vs Qwen） | `references/11-latest-qc-requirements.md` §7 标准 4 |

复跑脚本与原始输出在本目录：`run_static_check.py`、`inspect_4tasks.py`、`identity_check.py`、
`job_audit.py`、`validate_jobs_4tasks.py`、`summarize_errors.py`、`case_diff.py`、
`reference_audit.py`、`run-qc-static-result.json`、`inspect-result.json`、
`validate-jobs-result.json`、`probe-*.json`。

## 1. 总结论（四题不能全部通过）

| 题包 | A 甲方 static_check | B 甲方 inspect_delivery | C 甲方 validate_jobs | D 本机 local_checks | E 身份门 | F 区分度 | **判定** |
|---|---|---|---|---|---|---|---|
| 215 | ✗ FAIL | ✗ FAIL | **✗ FAIL（251 条）** | ✗ 3 项 FAIL | **✗ FAIL** | ✓ PASS | **不通过** |
| 216 | ✗ FAIL | ✗ FAIL | **✗ FAIL（319 条）** | ✗ 3 项 FAIL | **✗ FAIL** | ✓ PASS | **不通过** |
| 218 | ✓ PASS | ✓ PASS | ✓ PASS | ✓ 0 FAIL | ✓ PASS | ✓ PASS | **通过** |
| 219 | **✗ FAIL** | ✓ PASS | ✓ PASS | ✓ 0 FAIL | ✓ PASS | **✗ FAIL** | **不通过** |

## 2. 甲方 static_check 逐项明细（本次实测）

| 题包 | static_pass | errors |
|---|---|---|
| 215 | **False** | ① `task.toml has no docker_image`<br>② `referenced files are missing: solution\reference\wfmt, tests\test_wfmt_semantics.py` |
| 216 | **False** | ① `task.toml has no docker_image`<br>② `referenced files are missing: solution\reference\wchunk, tests\test_wchunk_semantics.py` |
| 218 | **True** | 无 |
| 219 | **False** | `referenced files are missing: tests/verifier/tests/, tests\verifier`<br>（warning：43 条 testcase > 27，不阻塞） |

### 2.1 逐条定性

| 条目 | 来源（实测定位） | 定性 |
|---|---|---|
| `task.toml has no docker_image`（215/216） | `task.toml` 无该字段；镜像在 `environment/Dockerfile` 的 `FROM` 中 pin 到 digest | **甲方要求已过时**。项目 2026-10-13 起规定 task.toml 不得写该字段（`known_issues.md` K29、`06-acceptance-gates.md` §0「已知差异」）。四包 Dockerfile 实际都 pin 到同一 digest，非 `latest`。218/219 反而因写了该字段而绕过此项，属**新旧范式并存** |
| `solution\reference\wfmt`（215）<br>`solution\reference\wchunk`（216） | `solution/solve.ps1:15,56` 与 `verifier/oracle/solve.ps1:15,56` 的**容错候选路径列表**：`$candidates.Add('C:\solution\reference\wfmt')` | **检查器语义误读**。该路径是 Golden 阶段的平台注入点，本来就不必存在于包内；脚本会依次尝试 6 个候选。甲方正则把候选逐字面量当成必须存在的交付文件。**可规避**：改用运行时拼接（如 `'C:\' + 'solution\reference\' + $slug`）或 `Join-Path` 变量组合 |
| `tests\test_wfmt_semantics.py`（215）<br>`tests\test_wchunk_semantics.py`（216） | `tests/run_tests.ps1:35`（在 `tests\` 下寻找隐藏套件）；`verifier/negative_access_probe.ps1:28` 亦有同名引用 | **真缺陷（缺件）**。215/216 的 `tests/` 下确实没有这份平台投放副本（仅 `verifier/tests/` 有）；218/219 的 `tests/` 与 `verifier/tests/` 各一份且 sha256 相同。与 local_checks 第 3 项 FAIL 指向同一缺口 |
| `tests/verifier/tests/`、`tests\verifier`（219） | `verifier/negative_access_probe.ps1:110`（注释文本）与 `:121`（`Get-ChildItem -LiteralPath (Join-Path $TaskRoot 'tests\verifier')`，带 `-ErrorAction SilentlyContinue`） | **脚本残留引用**。该目录自 v1.1.0 起被有意删除（`REFIT-2026-10-13.md:166`「`tests/verifier/` 下的第二份重复副本删除」），探针脚本仍硬编码检查它。运行时容错、静态检查判缺失。**可规避**：注释去掉路径样式；代码先 `Test-Path` 或用变量拼接 |

### 2.2 static_check 中已通过的项目（四包一致）

顶层五件齐全；`environment/` 七件齐全；`tests/` 六件齐全；`solution/` 有 `solve.ps1`；
`task.toml`、`judge.toml` 可解析；身份一致（task.toml / source.json / rubric.json 的
task_id 相同）；`[task].version` 存在；`judge.toml:source_sha256` = `rubric.json` 实字节；
`required_testcases.json` ≥5 条、ID 唯一、同时含 F2P 与 P2P、每项带 group；
`environment/workspace/` 无 solution/golden/hidden_test/reward 类泄漏。

### 2.3 甲方 validate_jobs（job 归档层）——215/216 的大头在这里

| 题包 | pass | 错误数 | 说明 |
|---|---|---|---|
| 215 | **False** | **251** | 全部 12 个 job 均不合规 |
| 216 | **False** | **319** | 全部 14 个 job 均不合规 |
| 218 | **True** | 0 | — |
| 219 | **True** | 0 | — |

两份质检包副本（`_reference` 与 `qc-pkg-new`）结论**完全一致**。

**215 错误分布**

| 错误类型 | 条数 |
|---|---|
| testcase 状态非终态（`NONE`） | 192 |
| 缺失 `verifier/verifier.log` | 12 |
| `task_checksum` 与交付包不一致 | 12 |
| testcase 集合与 `required_testcases.json` 不符 | 12 |
| 缺失 `agent/trajectory.jsonl` | 6 |
| 模型 alias 不可识别 | 6 |
| `model-result.json` provenance 不完整 | 6 |
| `trajectory.jsonl` 为空 | 3 |
| Oracle / NOP 轮次识别为 0 | 2 |

**216 错误分布**

| 错误类型 | 条数 |
|---|---|
| testcase 状态非终态（`NONE`） | 266 |
| 缺失 `verifier/verifier.log` | 14 |
| `task_checksum` 与交付包不一致 | 14 |
| `model-result.json` provenance 不完整 | 8 |
| 缺失 `agent/trajectory.jsonl` | 6 |
| 模型 alias 不可识别 | 6 |
| `trajectory.jsonl` 为空 | 3 |
| Oracle / NOP 轮次识别为 0 | 2 |

**根因：215/216 的 job 归档是旧协议格式**，与 218/219 存在代际差异：

| 维度 | 215 / 216（旧） | 218 / 219（新） |
|---|---|---|
| `verifier/result.json` 结构 | `schema_version: outside-harbor-result-v1` + `items[].passed: bool` | `cases[]` + `status: PASS/FAIL` |
| 甲方解析结果 | 读不到 `cases` → 状态记为 `NONE` | 正常解析 |
| `verifier/verifier.log` | **缺失** | 有 |
| `agent/trajectory.jsonl` | 部分缺失 / 部分为空 | 有且非空 |
| control job 的 oracle/nop 标识 | 甲方识别不出（计 0） | `ctl-oracle-*` / `ctl-nop-*` 正常识别 |
| job 目录命名 | 随机名 `task0__*` / `task__*` | 语义名 `model-qwen-1` 等 |

**历史对比（说明这不是新问题）**——`_qc_runs/qc-{215,216,218}-auto/model-jobs.json`：

| 包 | 历史 pass | 历史错误数 | 当前 pass | 当前错误数 |
|---|---|---|---|---|
| 215（旧版 v2.1.0） | False | 260 | False | 251 |
| 216（旧版 v1.2.0） | False | 302 | False | 319 |
| 218（旧版 v1.0.0） | False | 162 | **True** | **0** |

即 218 已通过返修解决，**而 215/216 的 job 层从未通过甲方校验**——`known_issues.md` K27
只登记了 `docker_image` 一项 FAIL，**未记录这 251/319 条**，属被低估的阻塞项。

### 2.4 甲方检查器中已过时 / 语义误读的要求

| # | 甲方要求 | 现状 | 性质 |
|---|---|---|---|
| 1 | `task.toml has no docker_image`（`static_check` 与 `inspect_delivery` 均判 error） | 项目 2026-10-13 规范要求该字段**不得存在**，镜像只在 Dockerfile pin digest；已登记为「已知差异」（`06-acceptance-gates.md` §0、K29） | **要求过时**。注意甲方工具包**内部不一致**：job 层（`validate_model_jobs.py`）已按 2026-10-13 规则更新，交付层未更新 |
| 2 | `standard-layout.md`「固定 14 个 job（Qwen 3 + Opus 3 + GLM 1 + Kimi 1 + Oracle 3 + NOP 3），少于即缺件」 | 甲方 `validate_model_jobs.py:116-120` 已改为「12（必需）或 14（含可选）都算合规」，注释写明「2026-10-13 起 GLM/Kimi 可选」 | **文档过时**（实现已更新，参考文档未同步）。故 219 的 12 个 job 合规 |
| 3 | 「脚本内出现的路径式字符串必须存在」 | 把 `solve.ps1` 的**容错候选路径**（`C:\solution\reference\*` 是 Golden 注入点）和探针脚本**注释里的路径样例**（`tests/verifier/tests/`）当作必须交付的文件 | **检查器语义误读**，只做字面存在性判断，不理解容错列表与注释。可通过改写脚本规避 |

## 3. 甲方 inspect_delivery 逐项明细

| 题包 | pass | errors / warnings |
|---|---|---|
| 215 | False | ERROR `Task has no pinned Docker image`；WARN 无 `source.json`（允许） |
| 216 | False | 同上 |
| 218 | True | WARN 无 `source.json`（允许） |
| 219 | True | WARN `required_testcases.json` 43 条 > 27，需人工复核范围 |

与 A 的差异：B 不检查脚本内引用，所以 219 在 B 下 PASS、在 A 下 FAIL；A 把
`docker_image` 缺失记为 error，B 记为 error 但项目已登记为已知差异。

## 4. 身份门（E）与逐 testcase（F）

### 4.1 身份门

`06-acceptance-gates.md` §0：**全部 job 的 `task_checksum` = 交付包的 Harbor dirhash**。

| 题包 | 包 dirhash | job `task_checksum` | job 数 | 唯一 | 一致 |
|---|---|---|---|---|---|
| 215 | `e29b36d0333757ef…` | `e5766a67f6346b56…` | 12 | 是 | **否** |
| 216 | `7c9e690e0d9db620…` | `d6d317c507752c0f…` | 14 | 是 | **否** |
| 218 | `a4e33ca3981e9014…` | `a4e33ca3981e9014…` | 14 | 是 | 是 |
| 219 | `8af4efbac29d722f…` | `8af4efbac29d722f…` | 12 | 是 | 是 |

215/216 的 job 内部干净（单一 checksum、无失败轮混入），但对应的包版本不是当前交付包
——跑分之后包内容又被改动过（215 的 `required_testcases.json` 现为 20 条，归档时记录 16 条）。
即 `known_issues.md` K28 登记的阻塞项，仍未解除，必须整批重跑。

### 4.2 逐 testcase 实测（回答「Qwen 的 testcase 是否比 Opus 少」）

对每个 job 的 `verifier/report.json` 逐 case 比对，统计三轮中通过的轮数：

**219（43 条 case）**

| 模型 | 逐轮 passed | 逐 case 通过轮数合计 |
|---|---|---|
| Opus | 43/43、43/43、43/43 | **129** |
| Qwen | 43/43、43/43、43/43 | **129** |

- 两者都通过：**43 条**
- Opus 通过 / Qwen 未通过：**0 条**
- Qwen 通过 / Opus 未通过：**0 条**
- 两者都未通过：**0 条**

→ **219 两个主模型逐 testcase 完全平手，0 条差异**，「Qwen 比 Opus 少通过若干 case」
在 219 **不成立**。其官方交付记录 `deliverables/2026-10-13_wpeimg219-返修/README.md:36`
已写「Opus 总分 3、Qwen 总分 3，逐 testcase 累计 129 vs 129 → **FAIL**」。

**218（26 条 case，供对照）**

| 模型 | 逐轮 passed | 逐 case 通过轮数合计 |
|---|---|---|
| Opus | 24/26、8/26、23/26 | **55** |
| Qwen | 10/26、22/26、23/26 | **55** |

- 两者都通过：23 条；都未通过：2 条
- **Opus 通过 / Qwen 未通过：1 条**（`f2p-trailing-bytes-reports-structure`）
- Qwen 通过 / Opus 未通过：0 条

→ 218 存在**极轻微**的逐 case 差异（1 条 case 仅 Opus 通过），但累计仍为 55 vs 55。
其官方记录 `deliverables/2026-10-13_wlogseg218-返修/README.md:36` 按甲方
「全模型零分平局」例外判 **PASS**。

结论：219 若要救回区分度，只能**新增判据**（使 Qwen 稳定失败而 Opus 通过），
无法通过调整逐 case 统计口径实现。

## 5. 甲方报告 9 条发现的内容层整改（仅 215/216 在报告内）

甲方 48 题报告**不含 218、219**（zq-id 表中 216 = 004 节、215 = 005 节，共 43 节 48 题）。
215 的 6 条、216 的 3 条内容层整改**均已落地**：

| 发现 | 整改证据 |
|---|---|
| ZQ005-01 / ZQ004-01 流式 8192 硬阈值 | 已删固定阈值，改 1/8 规模对照：`verifier/tests/test_wfmt_semantics.py:229-231`、`test_wchunk_semantics.py:232-240`；新增完整消费 + 尾部校验和用例 |
| ZQ005-02 / ZQ004-02 Kimi 配额失败混入能力分 | `jobs/invalid-slots.json` + `jobs/INVALID-SLOTS.md` 单列，归档树未改写 |
| ZQ005-03 / ZQ004-03 Windows 专属价值 | 新增 `verifier/WINDOWS_VALUE.md` 并归入通用编码题池 |
| ZQ005-04 声明 50% 评审权重无证据 | `rubric.json` 改 `programmatic-v3`，权重和 1.0、无 `llm_judge` |
| ZQ005-05 `judge.toml` 不可解析 | `tomllib` 全文件解析 PASS |
| ZQ005-06 隔离与负访问 | `verifier/ISOLATION.md` + `negative_access_probe.ps1`，实测 `verdict=PASS` |

**问题集中在格式/身份/区分度层，不是内容质量层。**

## 6. 遗留问题与建议

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | **215/216 的 job 归档整体不合甲方规范**（旧协议：`verifier/result.json` 用 `items[].passed` 而甲方要 `cases[]`+`PASS/FAIL`；缺 `verifier/verifier.log`；control job 无 oracle/nop 标识；模型 alias 不可识别；`trajectory.jsonl` 缺失或为空） | 甲方 C 门 FAIL **251 / 319 条**（最大阻塞项） | 按 218/219 的归档协议**重建 jobs/**：改用 `cases[]`+`status`、补 `verifier/verifier.log`、控制组用 `ctl-oracle-*`/`ctl-nop-*` 语义目录名与 role 标识。此项与第 2 项一并做（重跑时同时换用新组装流程） |
| 2 | 215/216 身份门 FAIL：job checksum ≠ 当前包 dirhash（`e5766a67…`/`d6d317c5…` vs `e29b36d0…`/`7c9e690e…`） | 硬门禁，不能交付 | 冻结包后整批重跑（控制组 + 模型轮次） |
| 3 | 215/216 `tests/` 缺平台投放副本（`tests\test_*_semantics.py`） | 甲方 A 门 FAIL + 本机静态 FAIL | 从 `verifier/tests/` 复制一份到 `tests/`（与 218/219 形态一致，两份 sha256 相同） |
| 4 | 219 `negative_access_probe.ps1` 引用已删除的 `tests\verifier` | 甲方 A 门 FAIL | 注释去掉路径样式；代码改 `Test-Path` 守卫或变量拼接 |
| 5 | 215/216 `solve.ps1` 容错候选含字面量 `C:\solution\reference\*` | 甲方 A 门误报 FAIL | 改为运行时拼接，避免被正则当作必须存在的交付文件 |
| 6 | `task.toml has no docker_image`（215/216） | 甲方 A/B 门 FAIL | **保持现状**（已登记为已知差异，不得为过检查写回字段） |
| 7 | 219 区分度 FAIL（Opus 3 = Qwen 3，逐 case 全同 129 vs 129） | 甲方门禁 | 新增只有强模型能完成、弱模型稳定失败的独立能力组（R11），再整批重跑 |
| 8 | 215/216 目录名版本（2.1.0 / 1.2.0）与包内身份（2.1.1 / 1.2.1）不一致 | 与「ZIP 内层根目录名 = `<task_id>-v<版本>-delivery`」冲突 | 确认飞书当前附件名后统一 |
| 9 | 218/219 根级保留 `REFIT-2026-10-13.md`，215/216 已移出包外 | 处置不一致 | 统一口径 |
| 10 | `_index/tasks_index.csv` 未同步（219 记 1.1.0/required 27，实物 1.4.0/43；215 记 16，实物 20） | 索引误导后续质检 | 按实物回填 |
| 11 | `known_issues.md` K27 只登记了 `docker_image` 一项 FAIL，未记录 215/216 的 251/319 条 job 层 FAIL | 阻塞项被低估 | 补登 K30，并同步 `06-acceptance-gates.md` |

## 7. 本次已执行的变更

1. 删除旧版题包，只保留最新包（依据 README「铁律四：换版即换目录」）：
   - 删除 `wfflab__wlogseg-218-v1.0.0-delivery`（288 个跟踪文件 + 32 个运行缓存残留）
   - 删除 `wfflab__wpeimg-219-v1.0.0-delivery`（75 个跟踪文件）
   - 保留 `wfflab__wlogseg-218-v1.1.0-delivery`、`wfflab__wpeimg-219-v1.4.0-delivery`
2. 新增本验证目录（脚本、原始输出、本报告）；`local_checks` 生成的 `probe-*.json`
   已从 `harbor-windows/` 根部移入本目录。
3. **未提交** git（按用户要求保留暂存状态）。
