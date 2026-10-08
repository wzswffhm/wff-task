# harbor-windows 题包质检报告（甲方 windows-harbor-qc 口径）

> **状态说明（2026-10-08 晚更新）**：本报告是**整改前**的质检快照。文中"标准 Harbor 直接加载 FAIL"已由 `../2026-10-08_harbor-windows-整改/` 修复并验证通过（两题 `is_valid_dir=True`、`harbor run --path <题包目录>` 直接加载、Dockerfile 自行构建、Oracle×3=VALID/1、NOP×3=VALID/0）。第五节 F3 一条已撤回更正。

- 质检对象：`harbor-windows/wfflab__wfmt-215`（v2.0.0）、`harbor-windows/wfflab__wreparse-217`（v1.0.0）
- 质检工具：甲方质检包 `windows-harbor-qc`（`_qc_ref/windows-harbor-qc`，与 `harbor-windows/_reference/windows-harbor-qc` 同一份）
- 执行环境：Windows 宿主机 + **Docker Desktop Windows 容器模式**（`desktop-windows`，server 29.7.2）+ Harbor CLI 0.22.0（`uv tool install harbor==0.22.0`）
- 执行时间：2026-10-08
- 输入题包**未被修改**（全程只读；所有兼容适配只发生在 `_qc_runs/staged/` 副本）

---

## 一、结论（先行）

| 维度 | wfflab__wfmt-215 | wfflab__wreparse-217 |
|---|---|---|
| 甲方静态结构检查 | 通过（仅 1 条**检查器误报**） | 通过（仅 1 条**检查器误报**） |
| 身份三元组一致（目录/task.toml/source.json/rubric.json） | PASS | PASS |
| required 集合唯一且含 F2P+P2P | PASS（15 = 8 F2P + 7 P2P） | PASS（24 = 13 F2P + 11 P2P） |
| **标准 Harbor 直接加载（交付形态）** | **FAIL（无法加载）** | **FAIL（无法加载）** |
| 目录级材料自洽（README/索引与实物一致） | **FAIL（见 D5）** | **FAIL（见 D5）** |
| 区分度（L3）准入口径 | **悬置**（包内 `qualified=true` 与 `known_issues` K18 冲突，见 D6） | 同左 |
| 动态门禁 Oracle ×3 | VALID/1 ×3（8/8 + 7/7） | VALID/1 ×3（13/13 + 11/11） |
| 动态门禁 NOP ×3 | VALID/0 ×3（F2P 0/8、P2P 7/7） | VALID/0 ×3（F2P 0/13、P2P 11/11） |
| 补齐兼容层后的整体判定 | **PASS** | **PASS** |

**一句话结论**：两题的**判分逻辑本身是正确、稳定且二值的**（真实 Windows 容器内 Oracle 全 1、NOP 全 0，NOP 下 P2P 全过、核心 F2P 全失败），但**交付形态不能被标准 Harbor CLI 加载**——按甲方清单 §7 属一票否决项，**当前不可直接进正式集**。修复面很集中（见第六节），不需要改动任何判分逻辑。

---

## 二、质检方法

1. 用甲方入口跑静态检查：
   ```powershell
   python run_qc.py --input <harbor-windows> --out <空目录>
   ```
   结果：两题各 1 条 `referenced files are missing`（已逐条证伪，见第五节），且入口脚本在静态 FAIL 时自身崩溃（见第五节 F3）。
2. 用 `harbor run` + 甲方 `windows_qc_env:WindowsQCEnvironment` 在**真实 Windows 容器**中执行 Oracle/NOP。每轮固定
   `--n-attempts 1 --n-concurrent 1 --max-retries 0`，每题独立 3 轮。
3. 判定复用甲方代码本身（`run_qc.classify_job / formal_result / dynamic_gate`），未自造口径。
4. 证据：每轮原始 Harbor CLI 日志、job/trial/verifier 原文、逐条 testcase 终态、reward 四件套。

**环境实测（容器内自证）**：`Microsoft Windows [Version 10.0.20348.5622]`，`ARCH=AMD64`，隔离 `hyperv`，网络 `none`，挂载数 `0`（QC 扩展按设计清空非日志挂载）。

---

## 三、动态门禁实测（最终证据：`_qc_runs/full-04`）

### wfflab__wfmt-215（required 15 = F2P 8 + P2P 7）

| 轮次 | Agent | 状态 | score | F2P PASS | P2P PASS | 退出码 |
|---|---|---|---|---|---|---|
| 1 | oracle | VALID | 1 | 8/8 | 7/7 | 0 |
| 2 | oracle | VALID | 1 | 8/8 | 7/7 | 0 |
| 3 | oracle | VALID | 1 | 8/8 | 7/7 | 0 |
| 1 | nop | VALID | 0 | 0/8 | 7/7 | 0 |
| 2 | nop | VALID | 0 | 0/8 | 7/7 | 0 |
| 3 | nop | VALID | 0 | 0/8 | 7/7 | 0 |

gate = `{"pass": true, "oracle_scores": [1,1,1], "nop_scores": [0,0,0], "nop_testcase_pass_count": 21}`

NOP 的 8 条核心 F2P 全部失败：
`f2p-sample-verifies`、`f2p-sample-roundtrip-is-byte-identical`、`f2p-sample-records-match-expected`、
`f2p-crc-matches-standard-check-value`、`f2p-tampered-content-is-rejected`、`f2p-checksum-covers-header-and-records`、
`f2p-truncated-container-is-reported-as-truncated`、`f2p-iter-records-is-streaming`

### wfflab__wreparse-217（required 24 = F2P 13 + P2P 11）

| 轮次 | Agent | 状态 | score | F2P PASS | P2P PASS | 退出码 |
|---|---|---|---|---|---|---|
| 1 | oracle | VALID | 1 | 13/13 | 11/11 | 0 |
| 2 | oracle | VALID | 1 | 13/13 | 11/11 | 0 |
| 3 | oracle | VALID | 1 | 13/13 | 11/11 | 0 |
| 1 | nop | VALID | 0 | 0/13 | 11/11 | 0 |
| 2 | nop | VALID | 0 | 0/13 | 11/11 | 0 |
| 3 | nop | VALID | 0 | 0/13 | 11/11 | 0 |

gate = `{"pass": true, "oracle_scores": [1,1,1], "nop_scores": [0,0,0], "nop_testcase_pass_count": 33}`

Oracle 原文（215）：`checks: 15 passed, 0 failed, 15 total` → `aggregate: score=1 weighted=1` → `===SWELIVE_GRADE score=1===`；
Oracle 原文（217）：`checks: 24 passed, 0 failed, 24 total` → `aggregate: score=1 weighted=1` → `===SWELIVE_GRADE score=1===`。

**奖励协议一致性**：两题的 `test.ps1` 在检测到 Harbor 日志根（`C:\logs`）后写出
`report.json`（`aggregate-v1`）+ `reward.txt`/`reward.json`/`reward-details.json`，
被 harbor 正常收集，`reward` 与 `formal_score` 严格一致——甲方 `formal_result` 判定为 `VALID`，无 `INVALID` 分支触发。

---

## 四、阻断项：交付形态无法被标准 Harbor 加载

三条独立缺陷，任一都会导致加载失败。证据为 Harbor 0.22.0 源码 + 可复现实验。

### D1 `[task]` 段缺少 Harbor 必填的 `name`

- `harbor/models/task/config.py` 的 `TaskPackageInfo.validate_name_format` 要求 `org/name` 形式；
  题包只写了 `[task] id = "wfflab__wfmt-215"`。
- 实测：`TaskConfig.model_validate_toml(task.toml)` 直接抛
  `ValidationError: task.name Field required`。
- 后果：`Task.is_valid_dir()`（`harbor/models/task/task.py:97-130`）捕获校验异常并返回 `False`，
  CLI 报 `No tasks matched ... There are 0 tasks available in this dataset`。

### D2 `[environment]` 缺少 `os` 与 `docker_image`

- 题包把镜像写在**顶层** `docker_image = "mcr.microsoft.com/windows/servercore:ltsc2022"`；
  Harbor 只读 `[environment].docker_image`（实测解析后 `docker_image=None`）。
- 题包未声明 `[environment].os`，Harbor 默认 `TaskOS.LINUX`；而 Windows 判定、`C:\logs`/`C:\tests`/`C:\solution`
  布局、`.bat` 入口选择全部由该字段派生。
- 后果：即使补上 `name`，Harbor 仍把该题当 **Linux** 题处理。

### D3 缺少 Harbor 在 Windows 下的入口名（`.bat`）

- `harbor/utils/scripts.py:23-25`：`SUPPORTED_EXTENSIONS = ['.sh', '.bat']`、`WINDOWS_EXTENSIONS = ['.bat']`；
  `harbor/models/task/paths.py:92-98`：Windows 的参考解路径固定为 `solution/solve.bat`。
- 题包只有 `solution/solve.ps1`、`tests/test.ps1`（符合甲方清单 §1，但不符合 Harbor 的发现规则）。
- 后果：`Task._validate_tests()` 因 `discovered_test_path_for(WINDOWS) is None` 抛 `FileNotFoundError`。

**四组对照实验（同一份题包，仅差一个文件）**

| 变体 | task.toml | tests/test.bat | `Task.is_valid_dir` |
|---|---|---|---|
| A 交付原样 | 原样 | 无 | **False**（解析即失败：缺 `name`） |
| B 补 name/os/docker_image | 已补 | 无 | **False**（缺 Windows 测试入口） |
| C 再补 `tests/test.bat` | 已补 | 有 | **True** |
| D 再补 `solution/solve.bat` | 已补 | 有 | **True**（Oracle 可执行的前提） |

### D4（结构性）题包绑定自家 runner 契约，而非 Harbor 契约

- `environment/adapter.toml`（`schema_version = "outside-harbor-adapter-v1"`）声明
  `task_root = C:\task`、`workspace_root = C:\task\environment\workspace`，并定义
  `prepare` / `validate` / `exec_agent` / `test` / `restore` / `cleanup` 六个生命周期钩子。
- 题包内所有脚本都按该布局写死路径（`test.ps1`/`run_tests.ps1`/`solve.ps1` 均以
  `<TaskRoot>\environment\workspace\...` 与 `<TaskRoot>\tests\hidden\...` 为基准）。
- Harbor 的布局是 `C:\solution`、`C:\tests`、工作目录（`environment/Dockerfile` 的 `COPY`）——
  **两者不兼容**；且 Harbor **没有 prepare 钩子**（217 的 `run_tests.ps1` 依赖
  `environment/prepare.ps1` 先在 `C:\wreparse-fixture` 造夹具，否则直接判 `INVALID: fixture manifest not found`）。
- 217 的 `environment/Dockerfile` 只有 `FROM` + `WORKDIR C:/task` + `CMD`，
  **不 `COPY` 工作区**（自家 runner 靠挂载）；Harbor 没有挂载工作区，因此镜像里根本没有候选代码。

### D5 目录级材料与实物不一致（文档/索引描述的不是本目录）

| 材料 | 声明 | 实物 |
|---|---|---|
| `README.md` | "**9 个题包**平铺于本目录下" | 只有 2 个题包（215、217） |
| `_index/tasks_index.csv` | 9 题清单（含已 `replaced` 封存的 `wsync-142` 等） | 表中题目均不在本目录 |
| `_index/model_summary.csv` / `model_validation_summary.json` | 只有 `wfflab__wtask-216` 的模型分数（3 题都不在本目录） | 与本目录 2 题无关 |
| `_index/known_issues.md` | K1–K20，覆盖 16 题的目录级已知问题（K13/K16/K17/K20 都是别的题的阻塞结论） | 本目录两题未被该清单收口 |
| `_index/EXTERNAL_IMAGES.json`、`checksums.sha256`、`validate-report.json` | 目录级镜像/校验/校验报告 | 与 2 题实物是否对应需甲方确认 |

→ 结论：**本目录当前不是一个自洽的交付单元**。归档时应同步裁剪索引类材料，或明确标注"本目录仅为 2 题子集"。

### D6 同一交付物内部对"可否交付"的结论互相矛盾

- `wfflab__wfmt-215/jobs/_index/qualification_summary.json`（生成于 2026-10-07T22:59）：
  `controls.passed = true`、`gates.qualified = true`、`opus_sum_greater_than_qwen = true`；
  `wfflab__wreparse-217/...`（2026-10-07T13:50）同样 `qualified = true`。
- `_index/known_issues.md` **K18**（2026-10-04 诊断）："**8.2 区分度在当前端点配置下无法满足**……全部 16 题均无法通过 8.2，本轮无题可交付"，根因指向 Opus 端点（`api.blvr.top` 401、`api.ebondai.com` 错误率 6.57% vs Qwen 0.41%）；K20 亦把 `wtask-216` 判为 FAIL。
- 两者时间差 3 天、结论相反（`known_issues` 未更新、或后续补跑后已翻盘，材料里没有说明）。

→ 结论：**区分度（L3）准入状态无唯一口径**，必须由甲方指定以哪份材料为准；这直接决定这两题是"可交付"还是"卡在 K18"。

---

## 五、甲方质检工具侧的问题（建议回传甲方）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| F1 | 静态检查把**运行期路径/文档示例/相对引用**误判为"缺失交付件"，只在 `task/`、`task/tests/`、`task/environment/` 三层查找 | 215 报 `assets\sample.wfmt`（实际在 `environment/workspace/assets/`）、`reference\wfmt`（在 `solution/`）、`logs\verifier\reward.json`（运行期产物）、`dev/null`、`4/5.`、`Python312\python.exe`；217 报 `Audit.ps1`/`Walker.ps1`/`WReparse.psd1`（在 `environment/workspace/WReparse/` 与 `solution/reference/WReparse/`）、`beta\zeta.txt`/`data\sample.bin`（prepare 夹具产物） | 两题被判静态 FAIL，直接挡住动态门禁 |
| F2 | `run_qc.py` 在静态 FAIL 时**自身崩溃**：`markdown_report()` 读 `task['static']['static_pass']`，但 `inventory` 条目里没有该键 → `KeyError: 'static'`，`report.md` 不会生成（`report.json` 已落盘） | 首次运行即复现 | 报告缺人读部分 |
| F3 | ~~`run_one()` 用 `--path <单题目录>` 导致 0 tasks~~ **【已撤回，2026-10-08 更正】** `harbor/cli/jobs.py:1774-1788` 显示 `--path` 会**先判断该目录自身是否为合法 task**，是则单题直跑；因此甲方脚本用法正确，`0 tasks` 的唯一原因是题包 `is_valid_dir=False`（即 D1–D3） | 见 `2026-10-08_harbor-windows-整改/README.md` 第二节 | 本条不是工具缺陷；题包整改后 `--path <题包目录>` 直接跑通 |
| F4 | `formal_result` 的 aggregate-v1 分支只认 `verifier/report.json`，与本题包写入协议一致，**该点无问题**（已实测 VALID） | `_qc_runs/full-04/report.json` | — |

> 注：F1 的**每一条**都已逐文件核对存在性（见 `static-missing-refs.md`）。

---

## 六、整改建议（最小改动，不动判分逻辑）

若要让题包通过标准 Harbor CLI（甲方门禁口径），建议在**新版本目录**内完成：

1. `task.toml`
   ```toml
   [environment]
   os = "windows"
   docker_image = "<已构建镜像的不可变引用>"      # 顶层 docker_image 不会被 Harbor 读取
   workdir = "C:\\testbed"                        # 与 Dockerfile 的 COPY 目标一致

   [task]
   name = "wfflab/wfmt-215"                       # Harbor 要求 org/name
   ```
2. 新增两个 Windows 入口（内容仅做委托，不改判分）：
   - `solution/solve.bat` → 调用 `solution/solve.ps1`，显式传 `-TaskRoot`；
   - `tests/test.bat` → 调用 `tests/test.ps1`，显式传 `-TaskRoot` / `-WorkspaceRoot`。
   注意 cmd 两个坑（本轮踩到并已规避）：`%~dp0` 尾部反斜杠会破坏引号解析（用 `"%~dp0."`）；
   括号块内的 `%ERRORLEVEL%` 在解析时展开（用 `if errorlevel N`）。
3. 让候选代码进入镜像：在 `environment/Dockerfile` 增加
   `COPY ["workspace/", "C:/testbed/"]`（或改为由平台挂载工作区）。
4. 217 额外需要：把 `environment/prepare.ps1` 纳入 `tests/` 入口链（Harbor 无 prepare 钩子），
   或把夹具构造合并进 `test.ps1`。
5. 统一 `C:\task` 布局与 Harbor 布局：建议脚本内部只依赖传入的 `-TaskRoot`/`-WorkspaceRoot`，
   不再硬编码 `C:\task\...`（本轮的 QC 适配层就是靠包装脚本搬运布局实现的）。
6. 修复后**升级 `task_version` 与 `task_hash`**，用新的空结果目录完整复跑 Oracle×3 + NOP×3（+ 模型区分度）。

> 若甲方认为"题包由平台侧适配（adapter.toml 即适配契约）"，则应明确质检包以 `adapter.toml` 为入口，
> 而不是要求题包满足 Harbor 原生布局——**两条路线必须二选一**，否则本轮这种"静态过、动态加载不了"的死结会重复出现。

---

## 七、判分质量评估（静态审查 + 实测）

| 检查项 | 215 | 217 |
|---|---|---|
| 五件套齐全（task.toml/instruction/environment/tests/solution） | PASS | PASS |
| solution 参考解存在且 Oracle 可执行 | PASS（`solve.ps1` + `reference/wfmt`） | PASS（`solve.ps1` + `reference/WReparse`） |
| 二值判分（无权重/部分分/LLM Judge） | PASS（`formal_score ∈ {0,1}`） | PASS |
| required 集合唯一、无重复、含 F2P+P2P | PASS | PASS |
| 题面 ↔ testcase 双向可追溯 | PASS（验收标准 A–F 对齐 15 条） | PASS（"必须满足的行为"1–8 + "用户可见验收"1–6 对齐 24 条） |
| 核心断言基于真实行为/终态（非源码正则、Diff、文件存在、日志文本） | PASS（pytest 行为断言） | PASS（导入模块后跑真实 NTFS 夹具断言） |
| P2P 初始即通过 | PASS（NOP 7/7） | PASS（NOP 11/11） |
| 核心 F2P 初始失败、Golden 后通过 | PASS（NOP 0/8 → Oracle 8/8） | PASS（NOP 0/13 → Oracle 13/13） |
| 隐藏测试/答案未泄漏给 Agent | PASS（Harbor 仅在 verifier 阶段上传 `tests/`；工作区只含可见冒烟测试） | PASS |
| 身份一致性（目录名 / `[task].id` / `metadata.task_id` / `source.json` / `rubric.json`） | PASS | PASS |
| 版本可追踪（非 `latest`） | PASS（2.0.0） | PASS（1.0.0） |

---

## 八、未闭合项与限制

1. **模型区分度（L3）本轮未按 Harbor 口径重跑**，且包内证据口径不一：
   - 包内**有**自家 runner（`outside-harbor-adapter-v1`）的逐作业证据：215 共 16 个 job
     （3 no-change + 3 golden + 10 candidate，覆盖 Qwen3.8-Max/GLM-5.3/Kimi K3/Opus 5）、
     217 共 17 个 job（3 + 3 + 11）；每个 job 含 `job.json`/`agent/run.json`/`verifier/result.json`（带 `verdict`）。
   - 汇总见 `jobs/_index/qualification_summary.json`：215 `Opus 2 vs Qwen 0`、217 `Opus 3 vs Qwen 2`，
     controls 均"no-change ×3 = 0、golden ×3 = 1"，`qualified = true`。
   - 但该证据**不是 Harbor 产物**，且与 `_index/known_issues.md` K18/K20 的"不可交付"结论冲突（见 D6）；
     215 另有 `extras/model_runs/`（`opus-5`、`qwen3.8-max-0902`、`_judge` 共 93 个文件），217 无 `extras/`。
   - 因此 L3 结论**悬置**，需甲方给定端点与口径后重跑。
2. **动态结论建立在 QC 适配层之上**：适配层（补 `name`/`os`/`docker_image`、`.bat` 包装、布局搬运、
   217 的 `COPY workspace`）只作用于 `_qc_runs/staged/` 副本，不改判分逻辑；因此实测证明的是
   "**判分逻辑正确**"，**不等价于**"交付原包在标准 Harbor 上可直接运行"（后者见第四节，结论为不可加载）。
3. 按要求全程**未使用 WSL**，Docker 走 `desktop-windows`；Harbor CLI 为 PyPI 0.22.0
   （另验证 0.24.0 对 `[task] name` 的要求一致）。
4. **交付面缺件（相对甲方质检包口径之外，但影响归档）**：两题均无 Harbor manifest/schema 声明、
   无 `delivery-extras` 一类的归档材料；215 的 `extras/` 与 217 的 `extras/` 不对称。
5. 复核建议：在甲方侧确认 F1/F3 与 D5/D6 的口径后，按第六节整改并重跑。

---

## 九、证据清单

| 路径 | 内容 |
|---|---|
| `report.json` | 最终逐轮判定（甲方 `formal_result` + `dynamic_gate`，12 轮） |
| `gate-summary.txt` | 门禁明细纯文本（逐轮 F2P/P2P 通过与失败清单） |
| `evidence/cli-logs/*.cli.log` | 12 轮 Harbor CLI 原始输出 |
| `evidence/verifier/<task>-<agent>-<n>/` | 每轮容器内判分产物原文：`report.json`（aggregate-v1）、`reward.txt`、`test-stdout.txt` |
| `static-inventory.json` | 甲方静态检查原始结果（含每文件 sha256、required 清单） |
| `static-missing-refs.md` | 静态误报逐条核对（存在性 / 运行期字符串出处与行号） |
| `adaptations/*.json` | QC 适配层逐条留痕（身份补全、Harbor 环境补全、入口包装） |
| `_qc_runs/full-04/jobs/**` | 完整 job/trial 目录（含 `trial.log`、`exception.txt`、agent 输出） |
| `_qc_runs/tools/*.py` | 适配与运行脚本（可原样复现本轮质检） |
