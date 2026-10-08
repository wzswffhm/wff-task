# harbor-windows 题包整改报告（标准 Harbor 契约）

- 整改对象：`harbor-windows/wfflab__wfmt-215`（v2.0.0）、`harbor-windows/wfflab__wreparse-217`（v1.0.0）
- 驱动口径：甲方质检包 `windows-harbor-qc`
- 执行环境：Windows 宿主机 + Docker Desktop **Windows 容器模式**（`desktop-windows`，server 29.7.2）+ Harbor CLI 0.22.0
- 整改日期：2026-10-08

---

## 一、结论

两题现已满足**标准 Harbor CLI 契约**，无需任何平台侧补丁即可加载、构建、评分：

| 验证项 | wfflab__wfmt-215 | wfflab__wreparse-217 |
|---|---|---|
| `Task.is_valid_dir()` | **True** | **True** |
| `harbor run --path <题包目录>` | **加载成功**（单题直跑） | **加载成功**（单题直跑） |
| 镜像来源 | `environment/Dockerfile` 由 Harbor 自行构建 | 同左 |
| 默认环境（**零扩展**）Oracle | **Reward 1** | 同左（同一入口契约） |
| Oracle ×3 | **VALID/1 ×3** | **VALID/1 ×3** |
| NOP ×3 | **VALID/0 ×3** | **VALID/0 ×3** |
| `jobs/` 记录数 | 22（16 历史 + 6 Harbor） | 23（17 历史 + 6 Harbor） |

---

## 二、根因更正：撤回上一版报告的 F3

上一版质检报告把"甲方 `run_one()` 用 `--path <单题目录>`"判为工具缺陷（F3），**该判断错误，现予撤回**：

```python
# harbor/cli/jobs.py:1774-1788
elif path is not None:
    is_task = Task.is_valid_dir(path, disable_verification=disable_verification)
    if is_task:
        config.tasks = [TaskConfig(path=path, ...)]   # 单题直跑
        config.datasets = []
    else:
        config.datasets = [DatasetConfig(path=path, ...)]  # 当 dataset 根扫子目录
```

即：`--path` **先判断该目录自身是否为合法 task**，是则直接单题运行。此前出现 `0 tasks` 的**唯一**原因是题包 `is_valid_dir=False`。甲方脚本用法没问题，题包不合规才是根因。用户"公司电脑能跑"的经验与此一致。

D1/D2/D3（缺 `[task] name`、缺 `[environment] os/docker_image`、缺 `.bat` 入口）依然成立，是本次整改对象。

---

## 三、逐项改动

### 三.1 两题相同

| 文件 | 改动 | 原因 |
|---|---|---|
| `task.toml` | `[task]` 增加 `name = "wfflab/<name>"` | Harbor 要求 `org/name`（`TaskPackageInfo.validate_name_format`） |
| `task.toml` | `[environment]` 增加 `os = "windows"` | 未声明时 Harbor 默认 `TaskOS.LINUX`，Windows 布局/入口选择全部由该字段派生 |
| `task.toml` | `[environment]` 增加 `workdir = "C:\\testbed"` | 与 Dockerfile 的 `COPY` 目标一致 |
| `task.toml` | **不设** `[environment].docker_image` | 让 Harbor 从 `environment/Dockerfile` 构建；顶层 `docker_image` 保留给本地 runner（Harbor 不读顶层键） |
| `solution/solve.ps1` | 新增 `-WorkspaceRoot` 参数 | 两种布局共用同一参考解：本地 runner 用 `<TaskRoot>\environment\workspace`，Harbor 用 `C:\testbed` |
| `solution/solve.bat` | **新增** | Windows 容器只发现 `.bat` 入口（`WINDOWS_EXTENSIONS = ['.bat']`），内容仅委托 `solve.ps1` |
| `tests/test.bat` | **新增** | 同上，委托 `test.ps1`，并显式传 `-TaskRoot "%SystemDrive%/"`（`C:\tests`）与 `-WorkspaceRoot "C:\testbed"` |

### 三.2 217 专属

| 文件 | 改动 | 原因 |
|---|---|---|
| `environment/Dockerfile` | 追加 `COPY ["workspace/", "C:/testbed/"]` | 原 Dockerfile 只有 `FROM`+`WORKDIR`+`CMD`（本地 runner 靠挂载），Harbor 无挂载，镜像里必须有候选工作区 |
| `tests/prepare.ps1` | **新增**（夹具构建器实现搬到此） | Harbor **没有 prepare 钩子**，而 `run_tests.ps1` 依赖 `C:\wreparse-fixture` 夹具 |
| `environment/prepare.ps1` | 改为转发到 `tests/prepare.ps1` | 本地 runner 的 `adapter.toml` 仍调用原路径，保持兼容；实现只有一份 |
| `tests/test.bat` | 先跑 `prepare.ps1`（缺夹具时）再跑 `test.ps1` | 承接 Harbor 缺失的 prepare 阶段 |

### 三.3 兼容性保证（不破坏本地 runner）

- 顶层 `docker_image`、`[metadata]`、`[agent]`、`[verifier]`、`[task] id/setup/test/golden`、`[policy]` 全部**原样保留**；
- `environment/adapter.toml` 未改动；
- `solve.ps1` / `prepare.ps1` 的**默认行为完全不变**（不传新参数时走原路径分支），只是新增了可选参数与转发层；
- 因此"本地 Outside Harbor runner"与"标准 Harbor"两套消费方式现在共用同一份题包。

---

## 四、两个 cmd/PowerShell 陷阱（本轮踩到并已规避）

1. **`%~dp0` 尾部反斜杠**：`robocopy "%~dp0" ...` 会让尾部 `\"` 逃逸引号，源路径解析错乱 → 一律写 `"%~dp0."`。
2. **括号块内的 `%ERRORLEVEL%`** 在解析期展开，不是运行时值 → 一律用 `if errorlevel N`。
3. **`-File` 参数不做引号解析**：`-TaskRoot "C:\"` 的尾反斜杠会吃掉收尾引号，单引号在 `-File` 下是字面量 → 传盘根用 `"%SystemDrive%/"`（正斜杠），`Resolve-Path 'C:/'` 正常归一为 `C:\`。

---

## 五、`jobs/` 记录：一处不重跑、一处必须跑

### 5.1 历史运行记录：**不需要重跑**，已用既有记录填充

`wff-task1/deliverables/2026-10-04_outside-harbor-win/runner/runs/` 保存着两题**完整的原始运行记录**（215 有 18 个 run、217 有 99 个 run），每个 run 含 `agent.log` / `checks.json` / `test.log` / `stderr.log` / `result.json`。

对账结果（`test_log_sha256` 与 runs 里的 `test.log` 逐条比对）：

| 题 | jobs/ 条目 | sha256 匹配 | 不匹配 | 结论 |
|---|---|---|---|---|
| 215 | 16 | **16** | 0 | 同源可验证 |
| 217 | 17 | **17** | 0 | 同源可验证 |

原先 `jobs/*/agent/run.json` 写的是"原始轨迹未随仓库留存，本文件为重述"。现在已把真实原始件填回 **33 条**记录（`agent/agent.log`、`verifier/checks.json`、`verifier/test.log`、`verifier/stderr.log`），并把 `artifacts_present` / `raw_log_present` 置为 `true`。**未重算任何判定**，`verdict` 与 sha256 保持原值。

### 5.2 Harbor 口径的门禁：**不能省**，已实跑

历史记录是**本地 runner**（`outside-harbor-adapter-v1`）的产物，不能证明"Harbor 能加载/能构建"。这两点必须实跑，已完成：

| 题 | Harbor Oracle | Harbor NOP | 记录落盘 |
|---|---|---|---|
| 215 | VALID/1 ×3（8/8 F2P + 7/7 P2P） | VALID/0 ×3（F2P 0/8、P2P 7/7） | 6 条 |
| 217 | VALID/1 ×3（13/13 + 11/11） | VALID/0 ×3（F2P 0/13、P2P 11/11） | 6 条 |

---

## 六、复现命令

```powershell
$env:DOCKER_CONTEXT="desktop-windows"

# 1) 加载 + 构建 + 判分（甲方与用户两种用法都可用）
harbor run --path .\harbor-windows\wfflab__wreparse-217 --agent oracle --n-attempts 1 --n-concurrent 1 --max-retries 0 --yes
harbor run --path .\harbor-windows             --include-task-name "wfflab__*" --agent nop --n-attempts 1 --yes

# 2) 不依赖任何 QC 扩展（默认环境）同样通过
harbor run --path .\harbor-windows\wfflab__wfmt-215 --agent oracle --n-attempts 1 --yes

# 3) 全新无缓存构建（验证"甲方能直接构建环境"）
docker --context desktop-windows build --no-cache -t qc/wfmt-215-fresh:test .\harbor-windows\wfflab__wfmt-215\environment
```

---

## 七、构建依赖与残留风险

### 七.0 决策记录：不预制依赖（2026-10-08）

已确认**甲方构建机有外网**，因此**不做依赖预制**，`environment/Dockerfile` 保持原样（`FROM mcr.microsoft.com/windows/servercore:ltsc2022` + 构建期联网安装）。理由：

- 预制会把 `FROM` 换成自有 tag，引入"甲方必须能拉到该镜像"的新前置条件，反而把"要外网"变成"要外网 + 要私有镜像"；
- 现状已实测可通过无缓存全新构建（见七.1），无需引入额外变量。

> 若后续甲方环境变为内网隔离，再启用预制方案；届时**必须重跑** Oracle×3 + NOP×3 —— 判分链路硬编码 `C:\Python312\python.exe` 且依赖 `pytest==8.3.5`/`pytest-json-report==1.5.0`，属二值判分，环境漂移会直接翻盘而非轻微抖动。

### 七.2 风险表

| 项 | 说明 |
|---|---|
| 215 构建需联网 —— **已确认可接受** | `docker build --no-cache` 在无任何层缓存的条件下**成功构建**（11 步全通过，`Successfully built 2a159e2de92b`）。构建过程中实际联网获取：Chocolatey 2.7.4 + `git.install 2.56.0.2`、Python 3.12.9 embed + pip 26.2.1、`pytest==8.3.5` + `pytest-json-report==1.5.0`；第 9 步环境预检 `import pytest, wfmt` 通过。甲方构建机有外网，故维持现状。 |
| 217 构建无需联网 | Dockerfile 仅 `FROM servercore:ltsc2022` + `COPY workspace/`，无 `RUN` 下载步骤。 |
| 215 层缓存 | 本机因已有同 Dockerfile 的镜像而层缓存命中（每轮 trial 约 20s）；甲方首次构建耗时取决于外网带宽。 |
| 本地 runner 未回归 | 本轮未运行本地 runner（其代码不在本工作区），兼容性通过"保留原键 + 默认分支不变"保证，建议交付前跑一次回归。 |

---

## 八、交付就绪评估（2026-10-08 实测，用甲方 QC 包完整跑）

### 8.0 结论：**尚不满足交付要求**

| 口径 | 状态 | 责任方 |
|---|---|---|
| 题包能被标准 Harbor 加载 / 自行构建 / 判分 | ✅ 达标 | 题包（已整改） |
| 动态门禁（用甲方自己的 `classify_job`/`formal_result`/`dynamic_gate`） | ✅ PASS（oracle 1/1/1、nop 0/0/0） | 题包（已整改） |
| **甲方 QC 包 `run_qc.py` 结论** | ❌ **FAIL** | **甲方工具缺陷（题包侧无解）** |
| 目录级材料自洽性 | ✅ **已修复**（2026-10-08，材料与 2 题实物一致） | 题包目录 |

甲方 QC 包对本目录的实测输出：`conclusion: "FAIL"`、两题 `static_pass: false`、`runs: []`（**动态门禁一次都没跑**）。证据：`evidence/qc-full-run-report.json`、`evidence/qc-full-run.cli.log`。

### 8.1 阻塞项 A：甲方 QC 静态检查误报（题包侧无解，必须甲方修）

**证据 1 —— 扫描规则是正则启发式**（`run_qc.py:133-146`）：对**所有** `.ps1/.psm1/.bat/.cmd` 全文抓"像路径的东西"（**含注释**），再只在 `task/`、`task/tests/`、`task/environment/` 三个基准下找文件（`run_qc.py:256-266`）。

```python
path_pattern = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.${}\\/-]+)+|[A-Za-z0-9_.-]+\.(?:go|ps1|psm1|json|toml|dll|exe|bat|cmd))")
```

**证据 2 —— 最小复现**（`_qc_runs/tools/repro_static_false_positive.py`，调用甲方自己的 `static_check`，fixture 形状照抄甲方自测）：

| 脚本内容 | 结果 |
|---|---|
| 空脚本（**甲方自测 `tests/test_run_qc.py` 用的就是空脚本**） | PASS |
| 注释里写 `# see docs\FORMAT.md` | **FAIL**：`referenced files are missing: docs\FORMAT.md` |
| `$python = 'C:\Python312\python.exe'` | **FAIL**：`Python312\python.exe` |
| `Join-Path $results 'checks.json'` | **FAIL**：`checks.json` |
| `Join-Path $root 'WReparse\WReparse.psd1'` | **FAIL**：`WReparse\WReparse.psd1` |

即：**任何真实题包都不可能通过该项** —— 题包脚本必然包含容器内路径、工作区相对路径与产物文件名。

**证据 3 —— 报错清单可逐条证伪**：

- 215：`Python312\python.exe`（镜像内路径）、`logs\verifier\reward.txt`（容器内运行时产物）、`assets\sample.wfmt`（**实际存在**于 `environment/workspace/assets/`，只是基准不含 `workspace`）、`checks.json`（运行时产物）、`dev/null`、`4/5.`（来自文案）
- 217：`WReparse\WReparse.psd1`、`Audit.ps1`、`Model.ps1`、`PathSemantics.ps1`、`Walker.ps1`（**全部实际存在**于 `environment/workspace/WReparse/`）、`checks.json`、`data\sample.bin`

**证据 4 —— 静态失败硬短路动态门禁**（`run_qc.py:476-481`）：

```python
if any(not item["static_pass"] for item in inventory["tasks"]):
    payload = {"conclusion": "FAIL", "tasks": inventory["tasks"], "preflight": None, "runs": []}
    return 1        # ← oracle/nop 一次都不跑
```

**证据 5 —— 整改前后同结论**：整改前即 `static_pass=false`（`deliverables/2026-10-08_harbor-windows-质检/static-inventory.json`），整改后仍 `false`，误报为同一批。**该 FAIL 不是本次整改引入的**。

### 8.2 阻塞项 B：甲方 QC 报告生成崩溃（第二个工具缺陷）

`markdown_report`（`run_qc.py:427`）按 `task['static']['static_pass']` 读取，但 `inventory["tasks"]` 存的是 `static_check()` 的**扁平返回值**（键为 `static_pass`）：

```python
lines.append(f"静态结构：`{'PASS' if task['static']['static_pass'] else 'FAIL'}`")   # KeyError: 'static'
```

后果：`report.json` 在崩溃前已写出（结论仍可读），但 `report.md` 永不生成，且**未捕获异常使退出码变 1** —— 即使在"静态 PASS + 动态 PASS"的正常路径上也会把 PASS 误报为失败。

### 8.3 阻塞项 C：目录级材料不自洽 —— **已于 2026-10-08 修复**

**原问题**：`harbor-windows/README.md` 声明"9 个题包平铺"并列出 `wsync-142 / wreserved-201 / wads-202 / …`
—— **其中没有本次交付的 215/217**；实物只有 2 题。`_index/`（`tasks_index.csv`、`known_issues.md` K1–K20、
`model_summary.csv`、`model_validation_summary.json`）同样按 9/16 题编写。该材料描述的是
**完整仓库（`wff-task1`，含 16 题）**的形态，未按当前 2 题工作区裁剪。

**修复内容**（全部按实物 2 题重算，数值取自磁盘；生成脚本
`_qc_runs/tools/align_index_materials.py`）：

| 文件 | 处理 |
|---|---|
| `README.md` | 题包清单 9 题 → 2 题；新增「范围声明」与「标准 Harbor 兼容」章节；重写单题结构树与校验说明（含 `task_hash` 规则） |
| `VALIDATION.md` | 「当前进度」按 2 题重写；第四节判分链路更正为**实际实现**（原文写的是旧骨架的 `grade.py` / `test_patch.diff` 路线） |
| `_index/tasks_index.csv` | 2 行；`task_hash` 改为可复现的**题包定义树哈希** |
| `_index/model_summary.csv` | 按 2 题四模型重建；`testcase_pass_sum` 由各 `jobs/<run_id>/verifier/checks.json` 逐条 `PASS` 计数得出 |
| `_index/model_validation_summary.json` | 2 题；机器键 `qwen3.8-max` / `opus-5` / `glm-5.3` / `kimi-k3` |
| `_index/model_validation_report.md` | 2 题；准入结论 215（2.0 > 0.0）、217（3.0 > 2.0） |
| `_index/validation_report.md` | 2 题；题级验收表新增「Harbor 加载/构建」列 |
| `_index/knowledge_tree_coverage_report.csv` | 12 个方向中覆盖 2 个 |
| `_index/EXTERNAL_IMAGES.json` | 10 题 → 2 题；记录本机 Image ID 与基础镜像 ID |
| `_index/known_issues.md` | 新增范围声明 + K1–K20 逐条适用性对照；题号对照改为本目录 2 题 |
| `_index/CHANGELOG.md` | 追加 2026-10-08 条目 |
| `_index/checksums.sha256` | 按 2 题范围重算（515 个文件，含 `jobs/`） |

**校验**（`_qc_runs/tools/verify_index_alignment.py`，可复跑）：

```text
[checksums] entries=515 actual=515 missing=0 extra=0 stale=0
[tasks_index] rows=2
  wfflab__wfmt-215     : f2p=8  p2p=7  task_hash OK
  wfflab__wreparse-217 : f2p=13 p2p=11 task_hash OK
  wfflab__wfmt-215     : qwen=0 opus=2 admission=PASS
  wfflab__wreparse-217 : qwen=2 opus=3 admission=PASS
[scope] unlabelled old-scope claims in current-state docs: 0
[scope] CHANGELOG.md declares scope: yes
[scope] known_issues.md declares scope: yes

RESULT: PASS — materials match the two packages
```

**未重算（已显式标注）**：`_index/validate-report.json` 仍是旧 9 题范围的产物——生成它的
`skills/harbor-windows/scripts/validate_package.py` 未随本目录交付。该事实已在 `README.md`、
`CHANGELOG.md`、`VALIDATION.md` 三处标注，须在正式验收前于当前 2 题范围重新生成。

### 8.4 建议

1. **必须由甲方修工具**：F1 降级为 warning（或修正查找基准、排除注释与容器内路径）、F2 改键路径。否则甲方 QC 对**任何**真实题包都恒为 FAIL，本题包无论怎么改都过不了；
2. 本目录材料按实际 2 题对齐（阻塞项 C），可立即执行；
3. 不建议为"通过"而把路径字面量拆成变量拼接来规避正则 —— 属于粉饰检查，且损害题包可读性。

### 七.1 无缓存构建实测输出（节选）

```
Step 3/11 : RUN ... iex (...chocolatey.org/install.ps1...); choco install git -y --no-progress;
 ---> Chocolatey v2.7.4 / git.install v2.56.0.2 [Approved] / Chocolatey installed 4/4 packages.
Step 4/11 : RUN ... python-3.12.9-embed-amd64.zip ... get-pip.py ...
 ---> Successfully installed pip-26.2.1
Step 6/11 : RUN & 'C:\Python312\python.exe' -m pip install --no-cache-dir 'pytest==8.3.5' 'pytest-json-report==1.5.0'
 ---> Successfully installed ... pytest-8.3.5 pytest-json-report-1.5.0 pytest-metadata-3.1.1
Step 9/11 : RUN ... & 'C:\Python312\python.exe' -c 'import pytest, wfmt'
 ---> (no error)
Step 11/11 : WORKDIR C:/testbed
Successfully built 2a159e2de92b
Successfully tagged qc/wfmt-215-fresh:test
```
