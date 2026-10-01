# remediation_and_retest —— wfflab__wproc-209

本题是 **`wfflab__wsync-142` 的替换题**（按《Windows 专项 Coding Bench 数据采购》第八章 8.2）。
本文件记录：替换动因 → 选题依据 → 建成过程 → 对照与复验。

- 题包版本：**1.0**　｜　`task_hash`：`d6f13ab8e16fb828bd4e203b85e327f28172ca0bdf1083fa7a145160704c82b8`
- 主方向：**进程与执行上下文**（12 方向中的第 6 个；原 9 题均未覆盖）
- 被测包：`wproc` 2.1.0（自建，非上游移植）

---

## 迭代 1 —— wsync-142 门槛不成立，决定替换（2026-10-01 晚）

### 现象

`wfflab__wsync-142` v2.1 在四个模型上的 VALID 结果：

| 模型 | `model_score_sum` | `testcase_pass_sum` |
|---|---|---|
| Opus 5 | 0.0 | 61 |
| Qwen3.8-Max-0902 | 1.0 | 70 |
| Kimi K3 | 1.0 | 24 |
| GLM-5.3 | 1.0 | 24 |

- 条件 ① `Opus > Qwen`：`0.0 > 1.0` → **不成立**（方向相反）
- 条件 ② 双 0 时比 testcase：Qwen 非 0，前提不成立；即便按 testcase 比，`61 < 70` 亦**不成立**

完整论证见 `../wfflab__wsync-142/extras/remediation_and_retest.md` 迭代 6 / 迭代 7。
核心结论：**该任务族不存在能把方向翻过来的难度档位** —— Qwen 在全部已测维度均 ≥ Opus，
继续抬难度只会同时压低两侧、不改变符号。故不再整改，改走替换。

### 替换选题的约束

| 约束 | 取值 |
|---|---|
| 主方向 | 必须落在 12 方向中**尚未覆盖**的一个 |
| 反事实判定 | 换到 Linux 后实现方式、根因、Evaluator 三者至少一者必须改变 |
| 判分 | **二值**（required F2P + P2P 全过 = 1.0），不得引入权重 / 部分分 / LLM Judge |
| 区分度来源 | 必须来自 Windows 平台语义，而非歧义、信息缺失或冷知识 |

---

## 迭代 2 —— 选定「进程与执行上下文」并实测其 Windows 语义

### 方向选择

原 9 题覆盖：文件同步、编码、路径、并发、包管理、注册表…等方向，
**「进程与执行上下文」为空白**。该方向天然满足反事实判定：
Windows 的 `Popen.kill()` 只作用于直接子进程、`communicate()` 依赖管道 EOF，
这两条在 Linux/Unix 上表现不同（Unix 有进程组与信号），换平台后实现与根因都会变。

### 先实测，后出题（`scripts/win_probe_proc.py`）

按纪律「先验证平台语义，再据此设计 required」，本机（Windows 11 23H2, x64）跑了 6 条假设，
**5 命中 + 1 刻意对照**：

| # | 假设 | 结果 | 说明 |
|---|---|---|---|
| P1 | 后代持有 stdout 写句柄时，`communicate(timeout)` 到点仍无 EOF → `TimeoutExpired` | **HIT** | 「明明结束了却被判超时」的机理 |
| P2 | `Popen.kill()` 只杀直接子进程，孙进程继续存活 | **HIT** | 「超时后进程还在跑」的机理 |
| P3 | `taskkill /F /T /PID <直接子进程>` 能连整棵树一起杀 | **HIT** | 参考解的终止手段 |
| P4 | 用 `stdout.read(4096)` 收输出 vs `read1(65536)` | **对照** | `read` 阻塞到读满 → 直接子进程退出时丢数据（实测 0 字节）；`read1` 拿到 `'parent-started\r\n'` |
| P5 | 直接子进程退出后再 `taskkill /T` 对其后代无效 | **HIT** | rc=128；终止必须在子进程存活时发起 |
| P6 | `taskkill` 后读取线程能立刻拿到 EOF | **HIT** | 支撑「先收输出、再判超时」的可行性与 0.5s 宽限 |

> P4 是**刻意保留的对照**：它解释了为什么参考解必须用 `read1`（读多少算多少）而不是 `read`（读满才回）。
> 若没有这条对照，很容易写出一个「在简单用例上能过、在子进程退出场景下静默丢数据」的读数实现。

---

## 迭代 3 —— 建成题包并跑通 L2

### 被测缺陷（base）

| 文件 | 缺陷 | 对应题面故障 |
|---|---|---|
| `wproc/runner.py` | `proc.communicate(timeout=timeout)` 等的是**管道 EOF**，后代持有管道时会被拖住 | 故障②（明明结束却被判超时） |
| `wproc/runner.py` | 超时分支返回 `output=b""`，丢弃截止前已产生的输出 | 故障③（超时后输出不见了） |
| `wproc/processes.py` | `terminate_process` 只 `proc.kill()`，后代失控 | 故障①（超时后进程还在跑） |

### 参考解（`solution/oracle.patch`，7799 B / LF）

- `processes.py`：启动加 `CREATE_NEW_PROCESS_GROUP`；`terminate_process` 在 Windows 上先
  `taskkill /F /T /PID`（60s 上限），失败再回落 `proc.kill()`。
- `runner.py`：把「读输出」与「等结束」**拆成两条独立事实** ——
  独立 daemon 线程用 `stream.read1(65536)` 持续收输出并置 `finished` 事件；
  主线程用 `proc.wait(timeout)` 等直接子进程退出；超时则终止；
  再 `finished.wait(0.5)` 给排空一点宽限，最后才用已收字节组装 `RunResult`。

### 13 条 required（6 F2P + 7 P2P）

| 组 | id | 断言的可观察行为 |
|---|---|---|
| F2P | `test_timeout_terminates_the_whole_process_tree` | 超时返回后后代已停（心跳冻结 + 不在进程表） |
| F2P | `test_timeout_terminates_a_deep_tree` | 四层深的进程链同样全部停止 |
| F2P | `test_timeout_preserves_output_emitted_before_the_deadline` | 截止前的 stdout 必须出现在结果里 |
| F2P | `test_timeout_preserves_large_output_emitted_before_the_deadline` | 512 KiB 输出不丢，且超时后及时返回（<20s） |
| F2P | `test_timeout_result_keeps_both_stdout_and_stderr` | stdout 与 stderr 的截止前内容都保留 |
| F2P | `test_finished_child_with_a_live_descendant_is_not_a_timeout` | 直接子进程已退出、仅后代持有管道时**不得**判超时（<12s） |
| P2P | `test_success_still_reports_exit_code_and_output` | 既有成功路径不变 |
| P2P | `test_nonzero_exit_code_is_still_preserved` | 非零退出码保留 |
| P2P | `test_merged_streams_are_still_collected_for_finished_children` | 已结束子进程的合并流仍被收集 |
| P2P | `test_cwd_is_still_honoured` | `cwd` 仍生效 |
| P2P | `test_large_output_of_a_finished_child_is_still_collected` | 已结束子进程的 256 KiB 输出仍完整 |
| P2P | `test_unrelated_processes_are_not_touched` | 终止一次运行不得波及无关进程 |
| P2P | `test_timeout_returns_promptly_when_there_are_no_descendants` | 无后代时超时必须及时返回（<15s） |

### 一次实证整改：P2P 判活手段撞 `WinError 32`

- **现象**：`test_unrelated_processes_are_not_touched` 在 base 上也失败。
- **根因**：初版判活用「删掉心跳文件、再看是否被重建」。在 pytest 进程内该文件被旁观进程持续持有，
  删除操作撞 `PermissionError WinError 32`；隔离脚本 `diag_bystander.py` 证明被测行为其实完全正常。
- **整改**：改用两个互不竞争的独立观测 —— `_alive(pid)`（`tasklist /FI "PID eq N"`）
  与 `_heartbeat_frozen(hb)`（mtime 是否冻结），彻底避开文件删除竞争。
- **复验**：base **6 failed / 7 passed**（正是设计意图：F2P 全失败、P2P 全通过）；golden **13 passed**。

---

## 迭代 4 —— L2 与可见测试复验（待补：对照证据矩阵）

| 复验项 | base（no-change） | golden |
|---|---|---|
| `l2_runner` 判定 | `VALID`　`score=0.0`　pytest_rc=1　grade_rc=1（89.5 s） | `VALID`　`score=1.0`　pytest_rc=0　grade_rc=0（69.9 s） |
| 隐藏测试 | 6 failed / 7 passed | 13 passed |
| 可见测试 `tests/test_wproc_basic.py` | 10 passed | 10 passed |

> 镜像未构建（`image_digest` 待回填）、多模型区分度结论待出，详见 `quality_review.md`。

---

## 遗留整改

| # | 问题 | 状态 |
|---|---|---|
| R-1 | 镜像未构建，`image_digest` 待回填 | 待平台侧 `docker build`（本机 Docker 未启用 Windows 容器模式） |
| R-2 | 本机 L2 判分采用复现版 `l2_runner.py`，非容器内 `tests/test.ps1` | 两者判分链路同构（同一 `grade.py` + 同一 `swelive_spec.json`）；正式验收以平台 harness 为准 |
| R-3 | `extras/evidence/` 对照矩阵（no_change ×3 / golden ×3 / clean_room / 3 反例 / 等价实现） | 生成脚本已就绪（`scripts/build_evidence.py`，已泛化为按包名自动定位变体），待模型运行结束后统一执行，避免与模型运行争抢 CPU 影响计时类用例 |
