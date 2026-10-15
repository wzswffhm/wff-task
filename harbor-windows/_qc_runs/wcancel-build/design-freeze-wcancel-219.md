# 设计定稿 — `wfflab__wcancel-219`（重叠 I/O 精确取消）

> 目标：替换飞书 219 槽位（record `reczz28N2IGu9XmA`，现为 `wfflab__wpeimg-219-v1.4.0`：
> 静态门 FAIL、Qwen/Opus 双满分 3/129 无区分度、机制门禁 FAIL 含 F6 自认句）。
> 生产技术口径：与 `wfflab__wspawn-218-v1.0.0-delivery` 完全同形（该包已过甲方 QC 五门）。

---

## 1. 选题与查重

- 机制族：**重叠（异步）I/O 的精确取消**——`CancelIoEx` / `CancelIo` / `GetOverlappedResult` / `OVERLAPPED`。
- 查重（飞书 159 条记录，2026-10-14 全量扫描）：
  - `CancelIoEx / 异步 IO 取消` → **零命中**
  - `IOCP / 完成端口` → 零命中（备选，本次不用）
  - 已占用族：句柄继承（218）、稀疏文件（215）、虚拟地址空间（216）、PE 映像（219 旧题）、ACL/DACL（113 命中）、重解析点（30）、保留名（28）、硬链接（13）
- 现有四题族分布：文件系统（215）/ 内存（216）/ 进程创建（218）/ 映像（219 旧）⇒ 本题落在**异步 I/O 与内核同步**族，无重叠。

## 2. 反事实判定（F2）

把目标 OS 换成 Linux/macOS，主要实现、错误根因、评测器是否基本不变？

**否。** 理由：
- 「按某一个挂起的 I/O 请求精确取消」在 Windows 上由 `CancelIoEx(handle, OVERLAPPED*)` 提供，
  与请求一一对应、可跨线程调用；取消后的终态由 `GetOverlappedResult` 报 `ERROR_OPERATION_ABORTED (995)`，
  对已完成的请求报 `ERROR_NOT_FOUND (1168)`。
- POSIX 侧无对等物：`aio_cancel` 只能作用于 `aio_read/aio_write` 族请求，语义与终态码都不同（`AIO_CANCELED/AIO_NOTCANCELED/AIO_ALLDONE`），
  对普通 fd 常直接返回 `AIO_NOTCANCELED`；`io_uring` 的取消（`IORING_OP_ASYNC_CANCEL`）是另一套模型；
  线程 + 信号/事件标志的模拟做不到「精确到某一请求、且能区分已取消与已完成」。**错误根因也只在 Windows 上成立**：
  用 `CancelIo` 只能取消**调用线程**在该句柄上发出的全部 I/O，跨线程调用时**返回 TRUE 但什么也没取消**。
- 评测器必须在真实 Windows 上运行：它要自己用 `CreateNamedPipeW`+`CreateFileW`（`FILE_FLAG_OVERLAPPED`）建重叠对象、
  自己发挂起 `ReadFile`、自己从另一个线程调取消，并以 `GetOverlappedResult` 的原始错误码为终态——换 OS 一条都无法复算。

## 3. 实测判据（2026-10-14，Windows 宿主机探针 `_qc_runs/wcancel-build/probe-cancelio.py`）

| # | 操作 | 实测结果 | 用途 |
|---|---|---|---|
| P1 | 命名管道 + 重叠 `ReadFile`（无数据） | `False / 997 ERROR_IO_PENDING` | 构造「必然挂起」的请求 |
| P2 | **跨线程** `CancelIo(handle)` | 返回 **True**，但请求仍挂起（`996 ERROR_IO_INCOMPLETE`） | ★ 缺陷版「谎报成功」的直接依据 |
| P3 | `CancelIoEx(handle, &ov)` | True；`GetOverlappedResult` = `False / 995` | 正解的精确取消 |
| P4 | 同句柄两个挂起请求，只取消 A | A=`995`；B 仍 `996`；client 写入后 **B 正常完成 12 字节** | ★ F2P 核心：精确性 + 未取消请求仍可用 |
| P5 | 对**已完成**请求 `CancelIoEx` | `False / 1168 ERROR_NOT_FOUND` | 「不得谎报取消成功」 |
| P6 | **同线程** `CancelIo(handle)`（X、Y 两个挂起） | X、Y **都被取消**（`995/995`） | ★ 缺陷版「无法只取消一个」 |

> 结论：P2/P4/P6 三个对照构成「精确 vs 全体 vs 谎报」的完整判据，机制上不可能用跨平台实现蒙过。

## 4. 题目设计

| 项 | 内容 |
|---|---|
| 模块名 | `wcancel`（`environment/workspace/wcancel/`） |
| task_id | `wfflab__wcancel-219`，版本 `1.0.0`，难度 `L4` |
| 场景 | 采集器/构建器的异步读盘层：把大文件的读取切成多个重叠请求并行下发，支持"用户取消其中一个下载分片"——必须只取消那一个，其余的照常完成 |
| 公开 API | `submit(handle, size, offset=0) -> Request`；`cancel(request) -> bool`；`cancel_all(handle) -> int`；`wait(request, timeout=None) -> Completion`；`WCancelError`（`kind ∈ {unsupported, badarg, os, timeout}`）；`Completion(bytes_read, status)`，`status ∈ {"completed", "cancelled"}` |
| 必须写进题面的公开契约 | ① 取消必须**只**影响目标请求，同一对象上其它挂起请求仍须正常完成并交出正确字节；② 从**任意线程**调用取消都必须生效；③ 被取消的请求终态必须是 `status="cancelled"`（不得归类为 `os` 错误）；④ 对已经完成的请求调 `cancel()` 必须返回 `False`，不得谎报成功；⑤ 非重叠对象（未以 `FILE_FLAG_OVERLAPPED` 打开）必须 `WCancelError(kind="unsupported")`，不得静默退化；⑥ `wait()` 超时抛 `kind="timeout"`；无效句柄/参数抛 `kind="badarg"` |

### 4.1 缺陷版（`environment/workspace/wcancel/`，无引导性注释、无正确实现痕迹）

| 模块 | 缺陷 |
|---|---|
| `proc.py` 的 `cancel()` | 忽略 `request` 参数，直接 `CancelIo(handle)` ⇒ 同线程时把该句柄上全部请求一起取消；跨线程时返回 True 但什么都没取消 |
| `proc.py` 的 `wait()` | 把 `ERROR_OPERATION_ABORTED` 当普通 `os` 错误抛出，不产出 `status="cancelled"` |
| `proc.py` 的 `cancel()` 返回值 | 对已完成的请求也返回 `True` |
| `proc.py` 的 `submit()` | 不检查句柄是否以重叠模式打开（静默继续），非重叠对象不报 `unsupported` |
| `kinds.py` | `is_overlapped(handle)` 恒 `True`（谎报能力） |
| `errors.py` | `WCancelError` 已定义（公开契约），缺陷版只在部分路径使用 |

### 4.2 参考解（`solution/reference/wcancel/`）

直接使用 `kernel32!CancelIoEx`（按 `OVERLAPPED*` 精确取消，可跨线程）、
`GetOverlappedResult`（读取原始 `GetLastError`，把 `995` 映射为 `cancelled`、`1168` 映射为"未取消"）、
`CreateEventW`/`WaitForSingleObject` 做完成等待、`GetFileInformationByHandleEx`/`GetFileType` 或
`GetNamedPipeInfo` 判定对象类型与重叠能力；`submit` 前用 `GetFileInformationByHandleEx(FileModeInformation)`
或对非重叠句柄的 `ReadFile` 立即完成特征判定，确保非重叠对象报 `unsupported`。

### 4.3 testcase 计划（14 条 = F2P 7 + P2P 7，符合 5–27 区间）

F2P：
1. `f2p-cancel-affects-only-the-target-request`（P4）
2. `f2p-cancel-works-from-another-thread`（P2/P3）
3. `f2p-cancelled-request-reports-cancelled-status`（P3 的 995 → `status="cancelled"`）
4. `f2p-completed-request-cannot-be-cancelled`（P5）
5. `f2p-non-overlapped-handle-is-unsupported`（缺陷版谎报能力）
6. `f2p-cancel-all-cancels-every-submitted-request`（P6 的对照：`cancel_all` 才允许全取消）
7. `f2p-uncancelled-request-still-delivers-the-bytes`（P4 后半：B 读到 12 字节）

P2P：
1. `p2p-submit-leaves-request-pending`
2. `p2p-wait-returns-a-completion`
3. `p2p-wait-timeout-raises-timeout-kind`
4. `p2p-invalid-handle-is-rejected`
5. `p2p-cancel-returns-a-bool`
6. `p2p-request-can-be-resubmitted-after-cancel`
7. `p2p-visible-smoke-suite-still-passes`

### 4.4 环境层 preflight（F5 锚点：`environment/validate_environment.ps1`）

1. 主机内核是 Windows（`[System.Environment]::OSVersion.Platform -eq 'Win32NT'`），否则 `Fail`；
2. 能建命名管道并以 `FILE_FLAG_OVERLAPPED` 打开，能发出挂起 `ReadFile` 并读到 `ERROR_IO_PENDING`；
3. 能对挂起请求成功发出取消并读到 `ERROR_OPERATION_ABORTED`；
4. 保留原有 isolation audit（workspace 与隐藏材料的可达性）。
> 非 Windows / 非重叠能力 ⇒ 记 **INVALID**，不得输出正式 0 分。

## 5. 与 218 的生产形态对齐（必须逐项一致）

- 五件套平铺：`task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/`，另有 `verifier/`、`metadata/`、`source.json`、`jobs/`。
- `task.toml`：顶层 `docker_image` 钉 `@sha256`（与 `Dockerfile` 的 `FROM` 逐字一致）；`[policy]` 的 `mutable_paths` = `environment/workspace/wcancel`；`read_only_paths` 含 `environment/validate_environment.ps1`（**该文件必须真实存在**）。
- `tests/`：`test.ps1` + `test.bat` + `run_tests.ps1` + `aggregate_results.ps1` + `required_testcases.json`（顶层数组）+ `rubric.json` + `judge.toml`（`source_sha256` = `rubric.json` 实际哈希）+ 隐藏套件副本 `test_wcancel_semantics.py`（与 `verifier/tests/` 那份逐字节一致）。
- `verifier/`：`README.md` + `ISOLATION.md` + `negative_access_probe.ps1`（**含结果**）+ `rubric.conditions.json` + `oracle/`（与 `solution/reference/` 逐字节一致）。
- `metadata/windows_mechanism.json`：`counterfactual.answer="否"`；`exclusive_declaration.quote` 逐字取自 `instruction.md`；`mechanisms` ≥3（每条 `instruction_quote` 逐字 + `test_ref` + 一条 F2P）；`non_windows_must_fail.file = "environment/validate_environment.ps1"`。
- **包内严禁出现** `REFIT-*.md`、`verifier/WINDOWS_VALUE.md`、`oracle.patch` 等非交付文件（219 旧题的 F6 命中正来自 REFIT/WINDOWS_VALUE）。
- 跑分：`ctl-oracle-1..3`（3×1）+ `ctl-nop-1..3`（3×0）+ `model-qwen-1..3` + `model-opus-1..3` = **12 个 job**；区分度要求 `sum(Opus) > sum(Qwen)`，或总分相等时 Opus 的 testcase 累计严格更多。
- 流程铁律：**定稿 → 预打包 → 甲方 `windows-harbor-qc` 自检 PASS → 冻结 → 跑分 → 组装 `jobs/` → 交付**；自检 PASS 后改一个字节即全部 `task_checksum` 失效。

## 6. 飞书替换目标

- record：`reczz28N2IGu9XmA`（甲方ID 空、状态「待提交」、当前附件 `wfflab__wpeimg-219-v1.4.0-delivery.zip`，token `MNyTbCyMSoIfvvxA43Nclbkrnkh`）
- base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`
- 写回内容：附件（新 ZIP）+ 题目方向 + 提示词（题面）+ 返修原因 + 分数；**写操作需用户确认后执行**。
