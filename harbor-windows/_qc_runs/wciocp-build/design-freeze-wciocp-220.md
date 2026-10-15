# 设计定稿 — `wfflab__wciocp-220`（I/O 完成端口调度）

> 目标槽位：**220**（飞书表当前只有 215/216/218/219 四条记录，220 的记录待甲方分配后写回）。
> 生产技术口径：与 `wfflab__wcancel-219-v1.0.0-delivery` 完全同形（该包已通过甲方全量 QC，五项全 PASS）。

---

## 1. 选题与查重

- 机制族：**I/O 完成端口（IOCP）** —— `CreateIoCompletionPort` / `GetQueuedCompletionStatus` / 完成键（completion key）/ 重叠 I/O 的完成通知与多线程消费。
- 查重（飞书 159 条记录全量扫描，2026-10-14）：`IOCP / 完成端口` → **零命中**。
- 已占用族（本批四题）：稀疏文件（215）、虚拟地址空间（216）、子进程句柄继承（218）、重叠 I/O 精确取消（219）。本题落在**完成通知与内核级队列消费**族，与四题均不重叠。
- 与 219 的距离：219 判的是「取消某一个挂起请求」；本题判的是「**完成事件如何被集中、按完成键回传、并被多个线程各消费一次**」，二者的缺陷面与判据完全不同。

## 2. 反事实判定（F2）

把目标 OS 换成 Linux/macOS，主要实现、错误根因、评测器是否基本不变？

**否。** 理由：

- IOCP 是 Windows 独有的完成通知对象：句柄用 `CreateIoCompletionPort(handle, port, key, 0)` 绑定到端口并附带**完成键**；重叠操作完成时，内核把 `(完成键, OVERLAPPED*, 字节数)` 作为一个完成包**入队**；等待线程用 `GetQueuedCompletionStatus` **原子地取出**一个包。
- 关键性质是**内核级的唯一消费**：同一个完成包只会被某一个等待线程取到，多线程并发等待不会重复也不会丢失。POSIX 侧没有等价物：`epoll`/`kqueue` 只报告就绪而不承载「完成包 + 完成键」，`io_uring` 的 CQE 有自己的队列模型与 `user_data`，语义、错误码与线程消费规则都不同；用用户态队列 + 条件变量模拟，**必然**在多线程下出现重复消费或丢包。
- 错误根因也只在 Windows 上成立：缺陷实现之所以重复消费/丢包，正是因为它用进程内队列代替了内核完成端口。
- 评测器必须在真实 Windows 上触发：它要自己建可完成的对象、自己登记不同的完成键、自己用 K 个线程并发取包，并以「每个请求恰好被返回一次」为终态判据。

## 3. 实测判据（2026-10-14，Windows 真机探针 `_qc_runs/wciocp-build/probe-iocp2.py`）

| # | 操作 | 实测结果 | 用途 |
|---|---|---|---|
| P1 | 新建端口 + `CreateIoCompletionPort(handle, port, key, 0)` 绑定 | 返回同一 port 句柄，`err=0` | 绑定语义 |
| P2 | 提交 3 个重叠读（无数据） | 全部 `ERROR_IO_PENDING` | 构造挂起请求 |
| P3 | **3 个线程并发取包**，随后 client 写入 3 次 | `packets=3`、`keys={'0xaa'}`、`unique_ov=3`、全部来自本进程提交的请求 | ★ 内核级唯一消费 + 完成键回传 |
| P4 | **同一端口绑定第二个句柄**（键 0xBB） | `keys=['0xbb','0xbb','0xbb']`、`bytes=[1,2,3]`、`3/3` | ★ 跨句柄完成键区分 |
| P5 | 空端口等待 300ms | `ok=False err=258 (WAIT_TIMEOUT)`，耗时 0.31s | 超时语义 |
| P6 | `GetQueuedCompletionStatusEx`（批量取包） | 本机触发访问违规（`0xC0000005`），**设计不依赖该 API** | 已知环境限制 |

> 结论：P3 与 P4 是本题的判据核心——完成键由内核回传、完成包在多线程间唯一消费。用户态模拟无法同时满足这两点。

## 4. 题目设计

| 项 | 内容 |
|---|---|
| 模块名 | `wciocp`（`environment/workspace/wciocp/`） |
| task_id | `wfflab__wciocp-220`，版本 `1.0.0`，难度 `L4` |
| 场景 | 采集器的**完成通知层**：多个句柄（管道、文件）的重叠读都登记到同一个完成端口，K 个工作线程各自取包并按「完成键」把结果分派回它所属的作业——同一个完成包只能被一个线程取到，且取到的键必须是登记时给的那个 |
| 公开 API | `create_pool(threads=4) -> Pool`；`Pool.register(handle, key) -> None`；`Pool.submit(handle, size, offset=0) -> Request`；`Pool.take(timeout=None) -> Event`；`Pool.close() -> None`；`Event(key, request, bytes_read, status)`；`WCIOCPError(kind ∈ {"unsupported","badarg","os","timeout","closed"})` |
| 必须写进题面的公开契约 | ① `take()` 返回的 `key` 必须是 `register()` 时登记的那个值，**由完成机制本身回传**；② 同一个完成包在并发 `take()` 下**恰好被返回一次**（不重复、不丢失）；③ 同一端口上不同句柄的完成包各自带自己的键；④ `take(timeout)` 超时必须抛 `kind="timeout"` 且**不得丢弃**已到达的完成包；⑤ 未以重叠模式打开的对象 `register()` 必须抛 `kind="unsupported"`；⑥ `close()` 之后 `take()`/`submit()` 必须抛 `kind="closed"`，未完成的请求被取消；⑦ 无效参数/句柄抛 `kind="badarg"`，底层失败抛 `kind="os"` |

### 4.1 缺陷版（`environment/workspace/wciocp/`，无引导性注释、无正确实现痕迹）

| 模块 | 缺陷 |
|---|---|
| `pool.py` 的 `take()` | 不真正等待内核端口：把完成包放进**进程内列表**，多线程各自扫描并弹出 ⇒ 锁粒度不对时**同一个包被两个线程各取一次**（重复消费），线程多时还会丢包 |
| `pool.py` 的 `Event.key` | 不返回内核回传的完成键，而是按句柄查本模块自己维护的字典 ⇒ 同一句柄被重新 `register` 换键后，旧请求也报新键 |
| `pool.py` 的 `take(timeout)` | 超时路径会**清空**待取列表（顺手丢弃已到达的包） |
| `pool.py` 的 `register()` | 不检查对象是否为重叠模式，非重叠对象静默接受 |
| `pool.py` 的 `close()` | 只置一个标志，`take()` 仍能从残留列表返回包，`submit()` 也不报 `closed` |
| `wait.py` | 用 `WaitForSingleObject` + 轮询超时，作为上述模拟队列的等待实现 |

### 4.2 参考解（`solution/reference/wciocp/`）

直接使用内核完成端口：`CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)` 建端口、
`CreateIoCompletionPort(handle, port, key, 0)` 绑定并登记完成键、
`GetQueuedCompletionStatus(port, &bytes, &key, &ov, timeout_ms)` 原子取包
（超时得到 `WAIT_TIMEOUT(258)` ⇒ 抛 `kind="timeout"`，且不影响队列中已到达的包）、
用 `OVERLAPPED` 的唯一地址把完成包映射回 `Request`；
能力判定沿用内核文件模式（`ntdll!NtQueryInformationFile(FileModeInformation)`：异步对象 `Mode=0x0`、同步对象 `0x20`）。

### 4.3 testcase 计划（14 条 = F2P 7 + P2P 7）

F2P：
1. `f2p-completion-key-is-the-registered-one`（P3/P4：键由机制回传）
2. `f2p-each-completion-is-delivered-once`（P3：并发取包下不重复不丢失）
3. `f2p-keys-distinguish-handles-on-one-port`（P4：跨句柄键区分）
4. `f2p-timeout-does-not-drop-queued-completions`（P5 + 不丢包）
5. `f2p-non-overlapped-handle-is-unsupported`
6. `f2p-close-rejects-further-use`（`closed`）
7. `f2p-reregistered-key-does-not-rewrite-past-completions`（同句柄换键后，旧包仍报旧键）

P2P：
1. `p2p-register-binds-the-handle`
2. `p2p-submit-leaves-the-request-pending`
3. `p2p-take-returns-an-event`
4. `p2p-take-timeout-raises-timeout-kind`
5. `p2p-invalid-arguments-are-rejected`
6. `p2p-close-is-idempotent`
7. `p2p-visible-smoke-suite-still-passes`

### 4.4 环境层 preflight（F5 锚点：`environment/validate_environment.ps1`）

1. 主机内核是 Windows（`Win32NT`），否则 `Fail`；
2. 能新建完成端口，并把一个以 `FILE_FLAG_OVERLAPPED` 打开的命名管道绑定上去；
3. 能发出挂起 `ReadFile`，并在对端写入后从端口取到一个完成包，完成键与登记值一致；
4. 空端口等待超时必须得到 `WAIT_TIMEOUT(258)`；
5. 保留原有 isolation audit（workspace 与隐藏材料可达性）。
> 非 Windows / 无完成端口能力 ⇒ 记 **INVALID**，不得输出正式 0 分。

## 5. 与 219 的生产形态对齐（逐项一致）

- 五件套平铺 + `verifier/` + `metadata/` + `source.json` + `jobs/`（12 个）。
- `task.toml` 顶层 `docker_image` 与 `Dockerfile` 的 `FROM` 逐字一致并 pin digest；`[policy].mutable_paths = ["environment/workspace/wciocp"]`；`read_only_paths` 含真实存在的 `environment/validate_environment.ps1`；`withheld_from_agent` 含 `verifier`。
- `tests/`：`test.ps1` + `test.bat` + `run_tests.ps1`（slug 表 14 条）+ `aggregate_results.ps1` + `required_testcases.json`（顶层数组）+ `rubric.json`（5 组、权重和 1.0）+ `judge.toml`（`source_sha256` = `rubric.json` 实字节哈希）+ 隐藏套件两份逐字节一致。
- `metadata/windows_mechanism.json`：反事实=否、排他声明逐字锚定题面、≥3 条机制锚点（题面逐字 + `test_ref` + 一条 F2P）、`non_windows_must_fail` 指向 `validate_environment.ps1`。
- **包内严禁** `REFIT-*.md` / `verifier/WINDOWS_VALUE.md` / `oracle.patch`（F6 不可豁免）。
- 流程：定稿 → 预打包 → 甲方自检 PASS → **冻结** → 跑 12 轮 → 组装 `jobs/` → 打包 → 全量 QC → 写回。

## 6. 飞书槽位

- 目标：**220**。飞书表当前（2026-10-14 拉取）只有 `reczz28KwEOO3xHy`(215) / `reczz28KQU8reW2k`(216) / `reczz28MRVnWkD2v`(218) / `reczz28N2IGu9XmA`(219) 四条，**没有 220 记录**。
- 交付物先在本地做成 `wfflab__wciocp-220-v1.0.0-delivery` 并跑完全部门禁；写回待甲方分配 220 记录后执行（届时用 `base +record-upload-attachment` + `+record-batch-update`）。
