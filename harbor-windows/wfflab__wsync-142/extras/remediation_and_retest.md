# remediation_and_retest —— wfflab__wsync-142

本文件记录本题生产过程中实际发生的问题、根因、整改动作与复验结论。

## 迭代 1 —— 验证入口把“测试失败”误判为“候选级故障”

| 项 | 内容 |
|---|---|
| 现象 | 初版 `tests/test.ps1` 沿用骨架写法 `if ($testRc -ne 0) { 追加 ===SWELIVE_CANDIDATE_FAILURE ...=== }`。 |
| 根因 | pytest 退出码 `1` 表示“存在测试失败”，这是**候选的合法 0 分**；而 `> 1` 才表示中断/内部错误/收集失败。原写法会让 no-change 场景走 `candidate_failure` 分支，短路掉 F2P 明细判定，并把合法 0 分错误地归因成“编译或收集失败”。 |
| 整改 | 改为 `if ($testRc -gt 1)`；`grade.py` 沿用骨架未改，其 `candidate_failure` 语义因此与 pytest 语义对齐。 |
| 复验 | 见 `evidence/no_change/run-*/verifier/report.json`：`candidate_failure` 为 `null`，`FAIL_TO_PASS.failure` 列出各条 F2P，`score = 0.0`——0 分来自 required 未全部通过，而非基础设施故障。 |
| 结论 | 已修复并冻结。 |

## 迭代 2 —— 本机验证环境与镜像声明版本不一致

| 项 | 内容 |
|---|---|
| 现象 | 首轮本机验证使用的 pytest 为 9.1.1，而 `environment/Dockerfile` 锁定 `pytest==8.3.5`。 |
| 根因 | 环境不一致会使“本地已验证”与“容器内将运行”的可信度打折，违反规范 7.1“同一环境”原则。 |
| 整改 | 本机降级到 `pytest==8.3.5` + `pytest-json-report==1.5.0`，**重跑全部对照与反例验证**。 |
| 复验 | 重跑结果与首轮完全一致。 |
| 结论 | 已修复并冻结。 |

## 迭代 3 —— v1.0 区分度不达标，整体提高题目难度（version 1.0 → 2.0）

### 现象

v1.0（`task_hash = a06c9ab7…`，F2P 7 条 + P2P 9 条 = 16 required）在
Qwen3.8-Max-0902 / Opus 5 / Kimi K3 上**全部拿满分**：

| 模型 | 运行 | 状态 | 正式分 |
|---|---|---|---|
| Opus 5 | run-1 / run-2 / run-3 | VALID ×3 | 1.0 / 1.0 / 1.0（和 3.0） |
| Qwen3.8-Max-0902 | run-1 | VALID | 1.0 |
| Kimi K3 | run-1 | VALID | 1.0 |

（原始快照见 `extras/_v1_model_runs_snapshot.json`。）

### 根因

v1 的三条缺陷彼此独立、且每条都对应**一个函数里的一处局部改写**：
`path_key` 加 `os.path.normcase`、`remove_file`/`copy_file` 清只读属性、
`sync_tree` 加一层 `try/except OSError`。强模型可以一次性全部命中，
题目不构成区分度——按规范 8.2，`Opus.model_score_sum > Qwen.model_score_sum`
与“双 0 且 testcase 严格区分”两个条件都不成立，属**区分度不满足准入**，
应整改或替换。

### 整改：加入 8 条新的 required 行为（F2P 7 → 15，required 16 → 24）

新增要求全部来自**真实工程语义 / 跨文件状态 / 执行时序 / 环境约束 / 失败路径 /
多目标权衡**（规范允许的难度来源），并在 `instruction.md` 中完整声明，
不使用题面未声明的隐含要求或冷门单点陷阱：

| 新增 F2P | 难度来源 | 实测确认的 Windows 依据 |
|---|---|---|
| `test_readonly_empty_directory_is_pruned` | 环境约束 | 目录自身的只读属性使 `os.rmdir` 报 WinError 5，而 `prune_empty_dirs` 原本静默吞掉 `OSError` |
| `test_case_only_difference_between_file_and_directory` | 跨文件状态 | 路径比较大小写不敏感 + 同路径不能既是文件又是目录 → `os.makedirs` 报 `FileExistsError(183)` |
| `test_target_file_replaced_by_source_directory` | 跨文件状态 | 同上（大小写相同的情形） |
| `test_target_directory_replaced_by_source_file` | 执行时序 | 写文件前必须先整棵清掉同名目录（含其中只读子项） |
| `test_conflict_cleanup_keeps_unrelated_readonly_entries_intact` | 多目标权衡 | 清障只能作用于真正冲突的那条路径 |
| `test_same_size_and_mtime_but_different_content_is_updated` | 失败路径 | `shutil.copyfile` 不保留 mtime，上游就地改写并保留时间戳时签名完全一致 |
| `test_sync_is_idempotent_and_preserves_source_mtime` | 执行时序 | 复制 API 不保留源时间戳 → 第二次同步产生无谓动作 |
| `test_readonly_and_locked_target_entry_is_reported_without_abort` | 失败路径 | 只读+占用时清属性后仍为 WinError 32，必须与可修复的只读（WinError 5）区分 |

**设计前先做了 Windows 语义实测**（`skills/harbor-windows/scripts/win_probe.py`），
12 条假设中否决了 1 条：“只读目录挡住其子文件的删除”在实测中**不成立**，
因此没有把它写成用例——避免出现 no-change 也能通过的无效 F2P。

### 关键复验：v1 解法打不过 v2 的 required 集

把 v1 oracle 原样应用到 v2 的测试树上，**失败 7 条**：

```
test_readonly_empty_directory_is_pruned                        FAILED
test_case_only_difference_between_file_and_directory           FAILED
test_target_file_replaced_by_source_directory                  FAILED
test_target_directory_replaced_by_source_file                  FAILED
test_conflict_cleanup_keeps_unrelated_readonly_entries_intact  FAILED
test_same_size_and_mtime_but_different_content_is_updated      FAILED
test_sync_is_idempotent_and_preserves_source_mtime             FAILED
```

该结果同时作为反例对照固化在
`evidence/negative_and_equivalent_controls/negative_01_readonly_only/`（正式分 0.0）。

### 同步动作

`instruction.md`、`tests/test_patch.diff`、`solution/oracle.patch` 三件全部重写，
`task_version` 1.0 → 2.0，`task_hash` 重算为 `ec4941c1…`（后经迭代 5 修正，最终为 `7b56f240…`），
四处身份文件（`task.toml` / `tests/swelive_spec.json` / `platform_import.json` /
`extras/metadata/manifest.json`）同步，`image_ref` 改为 `…-v2.0`。
`environment/workspace/` 与 `environment/Dockerfile` **未改动**——新要求都能被
原 base 代码证伪，无需人为削弱实现。

## 迭代 4 —— 等价实现对照片暴露 dry_run 实现缺陷

| 项 | 内容 |
|---|---|
| 现象 | 首轮生成 `equivalent_01_alternate_impl`（结构不同的等价实现）证据时，该对照得 0.0 而非预期的 1.0。 |
| 根因 | 失败的是 P2P `test_dry_run_leaves_target_untouched`。排查后确认是**对照实现自身写错**：`dry_run` 分支里错误地复用了真实写入的处理器，导致“试运行”真的落盘。 |
| 整改 | 修正对照实现的 dry_run 分支（只登记动作、不执行）。 |
| 复验 | `equivalent_01_alternate_impl` 得 1.0，15 条 F2P + 9 条 P2P 全过。 |
| 结论 | 这不是题包缺陷，而是**反向证明了 P2P 用例确实在约束行为**：一份结构完全不同的实现（scandir 遍历 + sha256 比对 + 临时文件原子替换）只要行为正确即可满分，说明隐藏测试验收的是行为而非某种写法。 |

## 迭代 5 —— 两条大小写用例超出题面声明（由 Opus 的真实失败反查出来）

| 项 | 内容 |
|---|---|
| 现象 | v2.0 首轮真实模型运行中，Opus 5 `run-1` 判分为 18/24，其中 `test_case_only_difference_does_not_lose_file` 失败于 `assert ['Notes.TXT'] == ['notes.txt']`。 |
| 排查 | 该用例原本写死 `files_under(target) == ["notes.txt"]`，即**要求终态保留目标侧原有的名字大小写**。但 `instruction.md` 目标 2 与验收标准 2 只声明“该文件存在、内容为源中的内容、条目不多不少”，**从未规定终态用的是源侧还是目标侧的大小写**——而两者在 Windows 上本就是同一条路径。Opus 的实现把大小写不同的两个路径按内容就地更新/重建，终态名字取源侧的 `Notes.TXT`，是对题面的合法实现，却被测试判为失败。 |
| 根因 | 用例把**我方 oracle 的实现细节**（`path_key` 用 `normcase` 归一后按目标侧既有名字落盘，名字大小写保持目标侧原样）当成了验收要求，属**超出题面的过约束**。同一问题也存在于 `test_case_only_difference_identical_content_makes_no_change`（写死 `== ["readme.md"]`）。 |
| 整改 | 两处断言改为**大小写不敏感**的等价形式：`len(found) == 1` 且 `found[0].lower() == "<期望>"`，并同步在 docstring 中说明“题面不对名字大小写作规定”。`tests/test_patch.diff` 的 hunk 行数由 `+1,428` 更正为 `+1,440`，`git apply --check` 通过。 |
| 复验 | Opus 5 `run-1` 由 18/24 变为 **19/24**（正式分仍为 0.0，其余 5 条失败均为实质缺陷）。`no_change` 仍 0.0、`golden` 仍 1.0、3 个反例仍 0.0、等价实现仍 1.0 —— 放宽未削弱任何区分度。 |
| 版本 | 按 `task.toml` 中自定约定「影响 Tests 的修改必须升级 version」，`task_version` 2.0 → **2.1**，`task_hash` → `478e5057…`，`image_ref` → `…-v2.1`；题面与 oracle 未改动，环境（Dockerfile / workspace）未改动。 |
| 结论 | 已修复。这是一次由**真实模型运行反查出的测试公平性缺陷**：如果没有跑模型，这条过约束会一直隐藏，并可能把一个正确实现判成 0 分。 |

> 修正后的 5 条失败（Opus 5）均为实质缺陷，不在本轮整改范围：
> 目标目录被源文件取代、同名文件被源目录取代、清障不误伤无关条目这三条都在删除阶段报
> `WinError 3 系统找不到指定的路径`（先删了父目录又去删其子项）；另有
> 大小写不同 + 条目类型不同这一条未建立目录；以及未保留源文件修改时间。

## 遗留整改（不计入本轮验收）

| # | 问题 | 状态 |
|---|---|---|
| R-1 | 镜像未构建，`image_digest` 待回填 | 待平台侧 `docker build` 后回填（本机 Docker 未启用 Windows 容器，见 `_index/known_issues.md`） |
| R-2 | 本机 L2 判分采用复现版 `l2_runner.py` 而非容器内 `tests/test.ps1` | 两者判分链路同构（同一 `grade.py` + 同一 `swelive_spec.json`），但正式验收仍以平台 harness 为准 |

> 上述两项补齐后，须重新执行所有受影响环节，并升级 `task_version`。

## 迭代 6｜模型门槛方向不成立（2026-10-01 晚）

### 现象

v2.1 上四个模型的 VALID 运行结果：

| 模型 | 轮次 | score | pytest |
|---|---|---|---|
| Opus 5 | 3 | 0.0 / 0.0 / 0.0 | 19 / 20 / 22（共 24） |
| Qwen3.8-Max-0902 | 1（另 2 轮在跑） | 1.0 | 24 |
| Kimi K3 | 1 | 1.0 | 24 |
| GLM-5.3 | 1 | 1.0 | 24 |

门槛条件 1「`Opus.model_score_sum > Qwen.model_score_sum`」为 **0.0 > 1.0**，**方向相反**。

### 根因：Opus 补丁自身的实现缺陷（非题目问题）

以 `opus-5/run-3` 的补丁（10146 B）为例：

1. `build_plan` **只按 `source_files`（文件清单）建计划**，目录不单独建条目，
   靠写文件时 `_ensure_parent_is_dir` 隐式创建；
2. 同时，目标侧残留的旧文件 `data`（键 `data`）不在 `source_files` 中，
   被排成一条 **`DELETE`**；
3. 执行顺序是 **CREATE 在前、DELETE 在后**：CREATE `data/report.txt` 时
   `makedirs` 建出 `target/data/`；随后那条 `DELETE` 命中**同一条路径**
   （此刻 `os.path.isdir(entry.target)` 为真）→ `remove_tree` 把**刚建好的目录整棵删掉**；
4. 终态为空，正好对应断言 `assert [] == ['Data/report.txt']`。

三次运行失败项**同族**：`case_only 文件↔目录` 3/3、`file→dir` 3/3、
`dir→file` 2/3、`冲突不误伤` 2/3、`幂等+mtime` 1/3。

题面对应条款为**显式声明**（目标 4「再按源的类型和内容落地」、
验收标准 5「同步结束后目标上的类型与内容与源一致，含仅大小写不同的情形」），
故**不属测试过约束**；Kimi / GLM / Qwen 均能通过同一条用例。

### 为什么"继续加大难度"无法达成该门槛

- 条件 1 要求 Opus 总分更高，而 Opus 已为 0.0，加难度只会更低；
- 退到条件 2（双 0 时比 testcase 通过总数）时，Opus 目前均 20.3/24（84.7%），
  需要把 Qwen 压到低于 20.3/24 且 Opus 不掉更多；但**在本任务族上 Qwen 在全部已测维度均 ≥ Opus**
  （v1.0 双方同为 1.0 打平；v2.x 起 Qwen 全过、Opus 失手），
  不存在能把方向翻过来的难度档位。
- 结论：本任务族**无法满足方向性门槛**，按规范 8.2「分析后整改或替换」应评估**替换**该题。

### 遗留公平性隐患（本轮未触发，仍应修）

`test_case_only_difference_between_file_and_directory` 与
`test_conflict_cleanup_keeps_unrelated_readonly_entries_intact` 使用
`files_under(target) == [...]` **写死了终态路径的名字大小写**。
若某实现对目标路径统一做 `normcase` 小写化（题面并不禁止），
即使行为完全正确也会被判错 —— 与迭代 5 同源的**过约束**，应改为大小写不敏感比较。

## 迭代 7｜按规范 8.2 判定为「替换」并封存（2026-10-01 晚）

### 最终模型数据（v2.1，本机 L2 判分，全部 VALID）

| 模型 | run-1 | run-2 | run-3 | `model_score_sum` | `testcase_pass_sum` |
|---|---|---|---|---|---|
| Opus 5 | 0.0（19/24） | 0.0（20/24） | 0.0（22/24） | **0.0** | **61** |
| Qwen3.8-Max-0902 | 1.0（24/24） | 0.0（23/24） | 0.0（23/24） | **1.0** | **70** |
| Kimi K3 | 1.0（24/24） | — | — | 1.0 | 24 |
| GLM-5.3 | 1.0（24/24） | — | — | 1.0 | 24 |

### 门槛判定

| 准入条件（规范 8.2） | 计算 | 结论 |
|---|---|---|
| ① `Opus5.model_score_sum > Qwen.model_score_sum` | `0.0 > 1.0` | **不成立**（方向相反） |
| ② 两者 `model_score_sum` 均为 0 且 `Opus5.testcase_pass_sum > Qwen.testcase_pass_sum` | 前提不满足（Qwen 为 1.0）；即便按 testcase 比，`61 > 70` 亦**不成立** | **不成立** |

两个准入条件均不成立 → 本题**不可交付**。

### 处置：替换（不继续整改）

迭代 6 已论证本任务族不存在能把方向翻过来的难度档位（Qwen 在全部已测维度均 ≥ Opus），
继续抬难度只会同时压低两侧、无法改变符号。故按规范 8.2 走**替换**，
由同方向、同知识域的新题 `wfflab__wproc-209`（主方向「进程与执行上下文」）承接。

### 封存口径

- 本题包**保留在仓库中**作为过程证据，**不参与本轮交付**；
- `_index/tasks_index.csv` 中该题 `status` 标记为 `replaced`，`replaced_by = wfflab__wproc-209`；
- `testcase_pass_sum` / `model_score_sum` 按上表定稿，不再接受新的模型运行；
- 本节为本题最后一次迭代记录。
