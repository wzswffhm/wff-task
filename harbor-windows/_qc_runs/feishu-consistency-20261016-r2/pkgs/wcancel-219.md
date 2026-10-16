包 wcancel-219：C 项结论概览（PASS 8 / FAIL 3 / 待确认 0；另 C15 判 N/A）

C1: PASS — 隐藏套件只用 `from wcancel import (...)` 取题面公开契约的 5 个名称，断言只碰公开属性 status／bytes_read／kind，全文无 `_` 前缀私有符号、无 `wcancel.xxx` 内部属性访问 — 证据 `tests/test_wcancel_semantics.py:37-43`、`:140-141`、`:231`、`:276`
C2: PASS — 抽出的断言逐条能落到题面 A–G 条款，未发现题面外断言（对照表见下） — 证据 `instruction.md:27-59` 对照 `tests/test_wcancel_semantics.py:135-291`
C3: FAIL — 整题核心语义「内核里真的只停那一个请求」只有候选自己的 `wait()` 返回值作观测点，套件从不自行读内核终态 — 证据 `tests/test_wcancel_semantics.py:140-141`、`:58-71`；`verifier/README.md:11-17`
C4: FAIL — 题面条款 F 的「底层调用失败抛 `kind="os"`」在隐藏套件与可见 smoke 中都没有任何用例 — 证据 `instruction.md:53`；`tests/test_wcancel_semantics.py:273-291`；`environment/workspace/tests/test_wcancel_basic.py:168-265`
C7: PASS — 包内只有一条评分链（test.bat→test.ps1→run_tests.ps1→aggregate_results.ps1），`formal_score`／`verdict`／reward 三者同源同值且都是二值；`weighted_score` 只是诊断字段 — 证据 `tests/aggregate_results.ps1:112`、`:127`、`:142`；`tests/test.ps1:80-82`、`:98-99`
C8: PASS — 缺候选包、套件未注入、出现非 PASS/FAIL 状态都走 exit 2 且不写 reward，不会产生 VALID/0；唯一歧义路径是 `run_tests.ps1:177-183` 的 collected==0→全记 FAIL — 证据 `tests/run_tests.ps1:63-70`、`:157-159`、`:209-214`；`tests/test.ps1:30-33`、`:60-77`
C12: PASS — `instruction.md` 全文只讲 wcancel 的取消语义、现象与验收，无 DPAPI／文件流／其他题模板残留 — 证据 `instruction.md:1-63`
C13: FAIL — 题面第 9 行声称评测器「以内核报告的终态为准，不采信 wcancel 自己的返回值」，交付的判分实现恰恰只读候选 `wait()` 的返回值 — 证据 `instruction.md:9`；`tests/test_wcancel_semantics.py:141`、`:171`、`:201`
C14: PASS — 公开入口 submit／cancel／cancel_all／wait 与 Request／Completion／WCancelError 都有对应用例，题面范围（一个包、4 个入口）与 14 条用例基本对等，唯一条款缺口已记在 C4 — 证据 `tests/test_wcancel_semantics.py:135-291`；`environment/workspace/tests/test_wcancel_basic.py:168-173`、`:233-239`
C15: N/A — 题面明确把跨平台排除在验收之外，不存在「POSIX 行为保持不变」的要求，因此没有跨平台回归缺口 — 证据 `instruction.md:5-11`
C16: PASS — 失败项可逐一复核：失败断言原文和 pytest `-rA` 输出随包保存在 runs 记录里；`cases[]` 本身确实只有 test_id+passed，pytest JSON 报告在 `run_tests.ps1:216-217` 随临时目录删除 — 证据 `jobs/model-qwen-2/verifier/test-stdout.txt:12-15`、`:33`；`jobs/model-qwen-2/verifier/report.json:170-241`
C17: PASS — 构建期离线（vendored 依赖 + `pip --no-index`），包内无上游补丁下载地址（source.json 两个 URL 是 MS Learn 文档），jobs 轨迹无取源码／补丁痕迹；运行期是否禁网包内无声明，见不确定清单 — 证据 `environment/Dockerfile:9-11`、`:37-44`；`source.json:7-9`；jobs 全目录对 pip/git clone/curl/Invoke-WebRequest 无命中

### C2 对照表：测试断言 → 题面依据

| 断言（文件:行） | 题面依据 |
|---|---|
| `cancel(first) is True` 且邻居 `wait(second,0.4)` 抛 timeout（:140、:144-147） | 有，A `instruction.md:29-31` |
| 另一线程 `cancel` 返回 True 且终态 cancelled（:168-173） | 有，B `:35` |
| 未取消请求 `status=="completed"`、`bytes_read==len(payload)`（:188-189） | 有，A `:30` |
| 取消后 `status=="cancelled"`（:201） | 有，C `:39` |
| 取消后 `bytes_read == 0`（:202） | 隐含，C `:39`「反映实际完成字节数」，空管道挂起读的完成量为 0 |
| 已完成请求 `cancel(...) is False`（:213）、二次取消 False（:222） | 有，D `:44-45` |
| 非重叠句柄 `submit` 抛 `kind=="unsupported"`（:229-231） | 有，E `:49` |
| `submit(-1,16)` 抛 `kind=="badarg"`（:275-276） | 有，F `:53` |
| `wait` 超时抛 `kind=="timeout"`（:241-242、:268-270） | 有，F `:53` |
| `cancel` 返回 bool、`cancel_all` 返回 int≥2（:249、:285） | 有，A `:31`、D `:44` |
| `wait` 返回 `status`/`bytes_read`（:261-262） | 有，C `:39` 与 A `:30` |
| 可见冒烟套件仍通过（:293-309） | 有，G `:58` |

### C3 FAIL

- 问题：套件对「取消是否真的在内核生效」没有任何独立观测，只信候选 `wait()` 返回的 `Completion.status`；文档声称的内核终态读回（995/996/1168）在交付文件里不存在。
- 证据：
  1. `tests/test_wcancel_semantics.py:140-141` — `assert cancel(first) is True` / `assert wait(first, timeout=5.0).status == "cancelled"`（status 由候选产生）
  2. `tests/test_wcancel_semantics.py:58-71` — 套件只声明了 CreateNamedPipeW／CreateFileW／WriteFile／CloseHandle，全文无 GetOverlappedResult 或任何错误码读回
  3. `verifier/README.md:11-17` — 「reads the request's terminal state back from the kernel — 995/996/1168」「A value returned by the candidate is never used as the reference for its own correctness」，与实际文件不符（`verifier/ISOLATION.md:52-60`、`metadata/windows_mechanism.json:8` 同述）
- 影响：假阳性 —— 一个只在进程内记账（`cancel` 恒返回 True、`wait` 按内部状态合成 `Completion(0,"cancelled")`）而从不调用 CancelIoEx 的实现，仍可满足全部 14 条：邻居请求用真实 ReadFile 挂起即可拿到 timeout（:144-147），未取消请求的字节交付（:176-189）也需要真实 I/O，两者都不约束「被点名那一个请求」的内核终态。
- 修复方向：让套件自持 OVERLAPPED/hEvent 并用 GetOverlappedResult 读回 995/996/1168 后再断言 `status`，或按 C13 修正文档与题面表述。

### C4 FAIL

- 问题：题面条款 F 明确要求「底层调用失败抛 `WCancelError(kind="os")`」，但隐藏套件与可见 smoke 都没有任何用例触发或断言 `kind=="os"`；条款 C 的「bytes_read 反映实际完成的字节数」也只断言了 0（例如 `:202`），可构造的非零部分完成场景无用例。
- 证据：
  1. `instruction.md:53` — 「参数或句柄不可用时抛 `WCancelError(kind="badarg")`；底层调用失败抛 `WCancelError(kind="os")`；`wait()` 等待超时抛 `WCancelError(kind="timeout")`」
  2. `tests/test_wcancel_semantics.py:273-291` — 错误分类只有 badarg（:276）、timeout（:242/:270）两类，无 os
  3. `tests/test_wcancel_semantics.py:202` — `assert done.bytes_read == 0`，取消路径只覆盖「零字节完成」这一种
- 影响：覆盖不足 —— 候选在「底层失败必须归类为 os」这一条上可以完全不做，也不会被扣分（对错误分类偷懒属假阴性漏检）。
- 修复方向：补一条能稳定触发底层失败的用例（如对只写句柄或无效读句柄 submit 后 wait），断言 `kind=="os"`。

### C13 FAIL

- 问题：题面第 9 行对评测方式的描述与交付的判分实现不符：题面称不采信候选返回值、以内核报告的终态为准，实际套件的终态断言全部取自候选 `wait()`。
- 证据：
  1. `instruction.md:9` — 「评测器会自己持有对象、自己发起挂起读取、自己从另一个线程发起取消，并以内核报告的终态为准，**不采信** `wcancel` 自己的返回值。」
  2. `tests/test_wcancel_semantics.py:201`（另见 :141、:171）— `assert done.status == "cancelled"`，`done` 是候选 `wait()` 的返回对象
  3. `metadata/windows_mechanism.json:8` — 「以 GetOverlappedResult 的原始错误码为终态」；`verifier/ISOLATION.md:52-60` 同述，交付套件无此调用
- 影响：题面与判分实物不一致（夸大评测独立性），并掩盖 C3 的观测缺口；Windows 平台语义本身（CancelIoEx／CancelIo 差异、995/996/1168）未发现事实错误。
- 修复方向：二选一 —— 在套件里真正落地内核终态观测（与 C3 同一处修复），或把题面第 9 行与 metadata／README 表述改为与实现一致。

### 未覆盖/不确定

- C5／C6／C9／C10／C11／C18 按要求未展开（主流程负责）。顺带观察：`jobs/_index/assembly_report.json:1-111` 显示 12 个槽位齐全（nop 3×0、oracle 3×1、model 6 轮，cases_match_required 全 true），`jobs/invalid-slots.json:5-70` 记录了 2 次 provider-quota 无效尝试并已归档重跑；`verifier/evidence/golden`、`verifier/evidence/no_change` 两个目录存在但为空（`verifier/README.md:34-38` 自述，实际对照证据在 `jobs/`）；`environment/adapter.toml:30` 本地运行镜像写作 `servercore:ltsc2022`，与 `environment/Dockerfile:13`、`task.toml:18-21` 声明的完整 ltsc2022 不一致，与 C18 相关，请主流程裁定。
- 运行期是否禁网无法从包内证实：`adapter.toml` 无任何网络字段、`task.toml` 无网络策略，只能证实构建期离线与轨迹无取源码痕迹（C17 已按可证实部分判 PASS）。
- 我只做了静态读取与关键词检索，未执行任何命令／容器；`jobs/*/agent/trajectory.jsonl` 未逐行通读（仅对 pip／git clone／curl／Invoke-WebRequest 检索，无命中）。
- C3 修复前，这 14 条用例对「内核级精确取消」的判别力需人工确认（观测缺口本身已核实，能否被实际滥用取决于候选是否刻意伪报）。
- 隐藏套件两份副本（`tests/` 与 `verifier/tests/`）SHA256 均为 `CE598856452087EBE7063C959194FE5873C2F878338C1397C53609612EF44F2C`，与 `verifier/README.md:23-25` 声明一致。
