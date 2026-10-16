包 wciocp-220：C 项结论概览（PASS 5 / FAIL 5 / 待确认 1 / N/A 1）

C1: PASS — 隐藏套件只用公开入口，无任何 `_` 私有符号访问 — 证据 `tests/test_wciocp_semantics.py:34-37`（仅 `from wciocp import WCIOCPError, create_pool`）、`:152-338`（只调 `register/submit/take/close` 与 `Event.key/bytes_read/status/request`、`Request.handle/offset`）；这些名字见 `environment/workspace/wciocp/__init__.py:35-53` 与 `instruction.md:63`。附注：`test_visible_smoke_suite_still_passes` 依赖 workspace 布局，有 `instruction.md:62` 兜底。
C2: FAIL — 4 条题面未写明的断言落在门控组内 — 见下方对照表。
C3: PASS — 无「候选自报即算过」的断言，无「仅计数>0 才核对」的条件断言 — 证据 `tests/test_wciocp_semantics.py:76-89,156-158,170-178,218-226`（测试自建管道、自写字节、自登记键后独立比对）；`_drain` 的 `except WCIOCPError: return`（`:135-136`）只会让事件变少并触发失败。附注：环境泄漏审计按固定文件名正则枚举（`environment/validate_environment.ps1:220-221`、`verifier/negative_access_probe.ps1:34-35`），改名可绕过，但不参与判分。
C4: FAIL — 题面 D2、F2、F3b 三条可验收行为无用例 — 见下方映射表；`cancelled` 在两份套件中各出现 0 次（`Select-String` 计数）。
C7: PASS — 平台入口唯一、规则一致 — `task.toml:51` 指向 `tests/test.ps1`；`tests/test.bat:15`、`environment/run.ps1:22-26` 均为委托；`tests/aggregate_results.ps1:77`（`$score`，items 全过）与 `:112`（`$formalScore`，cases 全过）因 rubric 的 14 个 id 与 14 个 case 一一对应（`tests/rubric.json:12-59`）而恒等，实测两者同值（`jobs/ctl-nop-1/verifier/report.json:10,86`）。
C8: FAIL — 「收集数为 0」被当成候选功能失败，输出 `VALID/0` 并写 reward — 见下方详情。
C12: PASS — `instruction.md` 67 行全属本题范围，无无关技术约定与模板残留 — 证据 `instruction.md:1-67`（范围 `:7-13`、现象 `:15-21`、验收 `:27-63`、提交 `:65-67`）。
C13: FAIL — 现象 5 与包内基线不符；F 小节 closed 与 cancelled 两条互斥 — 见下方详情。
C14: FAIL — 15 条可验收子项只固化 11 条，满分不足以支撑 F 组整体结论 — 同 C4 映射表；`tests/rubric.json:45-49` 的 timeout-and-close 组无 cancelled 用例。
C15: N/A — 题面明确排除跨平台，不存在「要求 POSIX 不变却无回归」 — 证据 `instruction.md:9,13`；反方向有保护：非 Windows 上 `pytest.skip`→`INVALID`→exit 2（`tests/test_wciocp_semantics.py:28-32`、`tests/run_tests.ps1:159,209-212`）。
C16: PASS — 失败项可逐一复核 — `tests/run_tests.ps1:114` 的 `-rA --tb=short` 输出随包保存，`jobs/ctl-nop-1/verifier/test-stdout.txt:11-36` 含断言行号与期望/实际值（如 `assert 1 == 2`、`expected [0,1000,…] observed [0,0,1000,…]`）。附注：`tests/aggregate_results.ps1:101-104` 的 `cases[]` 本身只有 `test_id`+`passed`；`pytest-results.json` 在 `tests/run_tests.ps1:216-217` 随临时目录删除，未随交付保存。
C17: 待确认 — 构建侧离线（`environment/Dockerfile:44` 用 `--no-index --find-links` 本地 wheelhouse），题面与包内无可下载上游补丁地址，6 份 model 轨迹中 `curl/git clone/pip/WebFetch/http` 命中数均为 0；但包内没有任何运行期禁网声明（`task.toml` 无 network 字段、`environment/adapter.toml` 无 `network_mode`，全包命中 0），运行期禁网由平台侧决定，静态不可核。

## C2 对照表（断言 → 题面依据）

| 断言 | 依据 |
|---|---|
| `event.key ==` 测试自登记的键 | 有 `instruction.md:31` |
| 重登记后已到达通知仍报旧键 | 有 `instruction.md:32` |
| 两句柄键互不串 | 有 `instruction.md:39-41` |
| 并发 take 下 6 个完成各恰好一次 | 有 `instruction.md:34-37` |
| 空端口 `take(timeout)` 抛 `kind=="timeout"` | 有 `instruction.md:45` |
| 非 overlapped 句柄抛 `unsupported` | 有 `instruction.md:51` |
| `close()` 幂等；关闭后 take/submit 抛 `closed` | 有 `instruction.md:55` |
| `register(-1,12)` 抛 `badarg` | 有 `instruction.md:57` |
| 可见冒烟套件仍通过 | 有 `instruction.md:62` |
| **`request.handle == 传入句柄`** | 无（仅 `instruction.md:63`「签名不变」；语义见 `__init__.py:49-50`） |
| **`event.bytes_read == 5`** | 无（题面未定义 bytes_read；见 `__init__.py:47`） |
| **`event.status == "completed"`** | 无（题面只提 `cancelled`，`instruction.md:56`） |
| **`take()` 首次必返回先提交者的键** | 无（题面未承诺返回顺序） |

## C4 映射表（条款 → 用例）

| 条款 | 用例（`tests/test_wciocp_semantics.py`） |
|---|---|
| A1 key 由机制带回 | `:152` |
| A2 重登记不改写已到达通知 | `:184` |
| B1 多线程恰好一次 | `:212` |
| B2 每次提交最终各取到一次 | `:212`（仅同句柄 6 次提交，弱覆盖） |
| C 多句柄各自带键 | `:161` |
| D1 空端口抛 timeout | `:280` |
| **D2 超时不得丢弃已到达通知** | **缺**（`:252-265` 先超时再提交，未测「先到达后超时」，与用例名不符） |
| D3 超时后端口不失效 | `:252` |
| E 不支持对象抛 unsupported | `:298` |
| F1 close 幂等 / closed | `:288`、`:268` |
| **F2 cancelled 完成交出** | **缺**（`cancelled` 命中 0） |
| F3a badarg | `:305`（仅一种形态；`solution/README.md:110` 称实测 11 种，未固化） |
| **F3b 底层失败 `kind=="os"`** | **缺** |
| G1 冒烟测试通过 | `:312` |
| G2 公开 API 签名不变 | 隐式（全部用例走公开面） |

## FAIL 项详情

**C2**
- 问题：三条用例断言了题面验收条款未写明的返回细节，且分属 `tests/rubric.json:12-17,24-28` 的门控组。
- 证据：`tests/test_wciocp_semantics.py:206` `assert request.handle == server`；`:245-246` `assert event.bytes_read == 5` / `assert event.status == "completed"`；`:198-199` `assert keys[0] == 1` / `assert keys[1] == 2`；题面 `instruction.md:29-63` 无对应表述。
- 影响：假阴性（合法重构若不再在 `Request` 上保留句柄原值或改变 status 取值，即掉 0.25/0.1 权重组）。
- 修复方向：把 bytes_read、`status=="completed"`、`Request.handle`、返回顺序写入题面验收条款，或改为与观测目标无关的宽松断言。

**C4**
- 问题：D2、F2、F3b 三条可验收行为完全无用例；D2、F2 是 issue 现象 3/5 的核心，且被 verifier 侧文档声称已验证。
- 证据：`tests/test_wciocp_semantics.py:252-265` 只覆盖 D1/D3；`cancelled` 在两份套件命中 0；`verifier/ISOLATION.md:66-67`「must hand that read back with `status == "cancelled"`」；`metadata/windows_mechanism.json:31` 把 F2P 用例指向 `:252-267`，而该区间未测「超时前已到达的通知」。
- 影响：假阳性（丢弃已到达通知、不做 cancel-on-close、把底层失败抛成无分类 `OSError`/`badarg` 都仍可满分）；覆盖不足。
- 修复方向：补 3 个用例——先到达后超时仍可取到、close 时未结束读取返回 `cancelled`、底层调用失败抛 `kind=="os"`。

**C8**
- 问题：`run_tests.ps1` 把「pytest 收集到 0 个用例」判为候选功能失败（14 项全 FAIL），aggregate 随后给出 `VALID/0` 并写 reward，与「harness 侧收集失败」不可区分；反向缺口是 pytest 退出码完全未检查。
- 证据：`tests/run_tests.ps1:177-182`（`if ($collected -eq 0) { status='FAIL' … 'the candidate package could not be imported' }`）；`tests/aggregate_results.ps1:111-112`（`$runValidity = if (… $invalidTotal -eq 0) { 'VALID' }`、`$formalScore = … { 1 } else { 0 }`）；`tests/test.ps1:74-82`（`VALID` 时写 `reward.txt`=`0`）；`tests/run_tests.ps1:114` 调 pytest 后未校验 `$LASTEXITCODE`。
- 影响：假阴性（隐藏套件语法错误、conftest 损坏、解释器 site 配置异常等 harness 故障被记成候选 0 分）；窄路径假阳性（pytest 内部错误被忽略）。
- 修复方向：「报告存在但 0 收集」与正常收集区分开并置 `INVALID`，同时在 pytest 调用后校验退出码。

**C13**
- 问题：① 验收 F 小节自相矛盾——`:55` 要求关闭后 `take()` 抛 `closed`，`:56` 又要求关闭时未结束读取以 `cancelled`「交出」，未给交付路径；② 现象段 `:21` 称「新的读取也照样能提交」，而基线关闭后 `submit()` 已抛 `closed`。
- 证据：`instruction.md:55-56`；`environment/workspace/wciocp/pool.py:124` `self._ensure_open()`（关闭后抛 `WCIOCPError(kind="closed")`），而 `:175-182` 的 `take()` 确实会先交出残留通知。
- 影响：假阴性（候选人按不存在或已满足的现象「修复」`submit`）与描述误导。
- 修复方向：在题面写明 cancelled 完成的交付方式，并修正现象 5 表述。

**C14**
- 问题：题面以「整个完成通知层符合 Windows 语义」为结论范围，15 条子项只固化 11 条，`formal_score=1` 不能支撑 F 组整体成立。
- 证据：`instruction.md:27-63` 对照上表；`tests/rubric.json:45-49`；`tests/required_testcases.json:1-16`（14 项中无 cancelled/os 用例）。
- 影响：覆盖不足被满分放大，形成假阳性结论。
- 修复方向：与 C4 同修，或收缩题面 F 组范围声明。

## 顺手观察（C5/C6/C9/C10/C11/C18，不展开）

- C5：三次 NOP 中 4 个 F2P 全部 FAIL，无 F2P 在空跑通过（`jobs/ctl-nop-1..3/verifier/report.json`）。
- C6：`ctl-oracle-1..3` 均 `VALID/1`、`ctl-nop-1..3` 均 `VALID/0`（`jobs/_index/assembly_report.json:3-56`），但 `verifier/evidence/golden` 与 `verifier/evidence/no_change` 为空目录（递归列目录计数 2、无文件），缺 golden/no_change 记录。
- C9：Opus 1+0+1=2 ＞ Qwen 0+0+0=0，非双满双零。
- C10：`jobs/model-opus-*/config.json` 声明 `model_name="claude-opus-5"`、端点 `https://4router.net`；Qwen 为 `qwen3.8-max-0902`。是否与要求型号一致需主流程按 C10 口径核对。
- C11：12 个 job 全部 `VALID`，无 invalid-slots 类文件；但 `jobs/config.json`（`job_name=ctl-nop-1`）与 `jobs/result.json` 是单次 trial 文件混放在 `jobs/` 根，与 12 trial 汇总并存，目录语义需主流程确认。
- C18：`environment/Dockerfile:13` 为 `windows/server:ltsc2022`（合规），但 `environment/adapter.toml:30` 与 `environment/agent_visible_paths.json:7` 用 `windows/servercore:ltsc2022`，两处镜像声明不一致，请主流程按 C18 口径裁定。

## 未覆盖 / 不确定

1. C17：运行期网络隔离由平台侧决定，包内无 `network_mode` 等声明，静态无法核实是否禁网。
2. C2 的 4 条断言能否由可见源码/文档（`__init__.py:35-53`）推导，取决于甲方对「题面外」的口径。
3. 文档漂移：`verifier/README.md:22` 声明两份套件 SHA256 为 `67126ff1…`，实测两副本均为 `23f356188f9b5012…`（`Get-FileHash -Algorithm SHA256`，两文件字节一致）；`verifier/README.md:28-29` 与 `solution/README.md:98` 写「F2P 7 / P2P 7」，而 `tests/required_testcases.json:2-15`、`tests/rubric.json:6`、`verifier/rubric.conditions.json:6`、`tests/judge.toml:12-14` 均为「F2P 4 / P2P 10」。不影响实测判分链路，但需确认以哪份为准。
4. `tests/run_tests.ps1:216-217` 删除临时目录，逐 case 的 pytest JSON 报告不随交付保存，失败明细只能从 `test-stdout.txt` 复核。
5. 未读：`environment/restore.ps1`、`solution/solve.ps1`、`verifier/oracle/solve.ps1`、两处参考实现源码、`environment/workspace/tests/test_wciocp_basic.py`、`environment/vendor/INVENTORY.json` 及各 job 的 `trial.log/job.log/lock.json/artifacts/manifest.json`；上述结论均不依赖这些文件。
