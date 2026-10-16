包 `wfflab__wspawn-218-v1.0.0-delivery`：C 项结论概览（PASS 5 / FAIL 5 / 待确认 2）

C1: PASS — 隐藏套件只 `from wspawn import` 六个题面公开名，无 `_` 前缀符号、无子模块或内部布局引用 — 证据 `tests/test_wspawn_semantics.py:31-38`、`instruction.md:63`
C2: PASS — 影响二值分的断言均可追到题面条款或候选可见面（README / 包 docstring / 可见冒烟测试），无纯题面外的硬门槛 — 证据 `instruction.md:29-63`、`environment/workspace/README.md:18-23`、`environment/workspace/tests/test_wspawn_basic.py:105`
C3: FAIL — 两条 F2P 用例实际观测不到泄漏，泄漏全部可继承句柄的基线 NOP 就跑过；`inheritable_handles` 的 P2P 断言亦形同虚设 — 证据 `tests/test_wspawn_semantics.py:266-286`、`:289-315`、`jobs/ctl-nop-1/verifier/report.json:17-22`
C4: FAIL — 题面 F 条 `unsupported` 分类、E 条 console/无法识别、C 条「不支持须报错」三条验收行为无任何用例 — 证据 `instruction.md:42`、`:51`、`:56` 对照 `tests/test_wspawn_semantics.py:383-405`
C7: PASS — 唯一计分实现是 `aggregate_results.ps1`，其余入口只做串联；rubric / required / 映射表三方为同一 14 条 id，规则统一二值 — 证据 `tests/aggregate_results.ps1:111-112`、`tests/rubric.json:12-60`、`tests/required_testcases.json:2-15`、`tests/run_tests.ps1:128-143`
C8: FAIL — 「一个用例都没收集到」被无条件判成候选人失败，链路最终产出 `run_validity=VALID` + `formal_score=0` — 证据 `tests/run_tests.ps1:172-183`、`tests/aggregate_results.ps1:100-112`、`tests/test.ps1:64-77`
C12: PASS — `instruction.md` 全文 67 行均为本题句柄移交内容，无模板残留、无别题技术约定 — 证据 `instruction.md:1-67`
C13: 待确认 — 现象 3/4 与冻结基线实测行为对不上（基线是抛 `kind="os"`，且泄漏方式是「全给」而非「句柄值错位」），是否改题面需人工判断 — 证据 `instruction.md:17-18`、`environment/workspace/wspawn/inherit.py:19-21`、`jobs/ctl-nop-1/verifier/test-stdout.txt:19`
C14: FAIL — 题面要求四类识别与 `unsupported` 分类，实际只覆盖 file/pipe，满分不能支撑 E/F 全部结论 — 证据 `instruction.md:51`、`:56` 对照 `tests/test_wspawn_semantics.py:383-395`
C15: PASS — 题面明确把 POSIX/跨平台排除在验收外，包内只有 Windows 用例并有非 Windows 拒绝路径 — 证据 `instruction.md:11`、`environment/validate_environment.ps1:26-28`、`tests/test_wspawn_semantics.py:25-29`
C16: FAIL — 落盘的 `cases[]` 只有 `test_id`+`passed`，逐 case 期望/实际值不在结构化记录里；pytest json 报告写在临时目录并被删除 — 证据 `tests/aggregate_results.ps1:101-104`、`jobs/ctl-nop-1/verifier/report.json:11-68`、`tests/run_tests.ps1:103`、`:217`
C17: 待确认 — 构建期明确离线，6 条模型轨迹无联网/取上游补丁痕迹，但包内无禁网声明，运行时出网策略无法静态判定 — 证据 `environment/Dockerfile:37-45`、`source.json:10`、`:14`、`environment/adapter.toml:27-34`

## C2 对照表（关键断言 → 题面依据）

| 断言（`tests/test_wspawn_semantics.py`） | 题面依据 |
|---|---|
| 列出的管道在子进程可用且内容回传（`:246-253`）、未列出的不跨进程（`:256-263`）、空 `inherit` 不带对象（`:266-286`）、两条中只交一条（`:289-315`）、清位后不跨进程（`:318-345`） | 有：`instruction.md:29-31`、`:36`、`:40-41` |
| `set_inheritable` 改变可外部观测的位（`:350-363`）、`is_inheritable` 与系统读数一致（`:366-378`） | 有：`instruction.md:40-41` |
| `handle_kind` 返回 `"pipe"`/`"file"` 字面值（`:383-395`） | 题面无字面值；可见面有 `environment/workspace/README.md:22`、`environment/workspace/wspawn/__init__.py:19-20`、可见冒烟 `tests/test_wspawn_basic.py:105` |
| `handle_kind(0)` 抛 `WSpawnError`，kind ∈ {os,badarg,unsupported}（`:398-405`） | 有：`instruction.md:52`、`:56`（测试放宽为三选一） |
| 退出码等于子进程退出码（`:410-413`）、文件对象作 stdout（`:416-422`） | 题面无；可见面有 `README.md:11`、可见冒烟 `:32`、`:41-46` |
| 非序列 argv / 空 argv / int inherit → `badarg`（`:425-434`） | 有：`instruction.md:57` |
| `inheritable_handles()` 是 list/tuple 且元素为 int（`:437-441`） | 题面只列名，元素类型无依据；弱旁证：可见冒烟 `:79-81` 只查容器类型 |
| `is_inheritable(...) is True/False` 严格布尔身份（`:366-378`） | 题面无「必须 bool」；弱旁证：可见冒烟 `:84-90` 仅在无效句柄分支查 `isinstance(value, bool)` |
| 可见冒烟套件继续通过（`:444-455`） | 有：`instruction.md:62` |

## FAIL 项明细

### C3 断言缺口 / 可被绕过
- 问题：三条整题关键断言缺独立观测，其中两条 F2P 用例连「泄漏」这一被测现象都观测不到。
- 证据：
  - `tests/test_wspawn_semantics.py:274-275` 空清单用例的子进程是 `python -c "import sys; open(sys.argv[1],'w').write('alive')"`，父进程持有的 `report_w`/`probe_w` 数值从未交给子进程，`:284` 只断言 `_read_until_eof(probe_r) == b""`；子进程即便继承了管道也无从写入，用例无法检出泄漏。
  - `tests/test_wspawn_semantics.py:297` 双管道用例只把 `report_w`、`first_w` 传给子进程，`second_w`（`:293` 创建、`:295` 置继承位）从未告知子进程，`:314` 的 `second_bytes == b""` 恒成立。
  - 实测佐证：泄漏全部可继承句柄的基线（`environment/workspace/wspawn/proc.py:61-68`，`close_fds: False` 且完全忽略 `inherit`）在 `jobs/ctl-nop-1/verifier/report.json:17-22` 中这两条即 `passed: true`（`ctl-nop-2/3` 同）；同文件 `:13-14` 显示真正能检出泄漏的只有 `test_unlisted_handle_does_not_cross_the_boundary`（它把 `probe_w` 的数值交给了子进程）。
  - 第三条：`tests/test_wspawn_semantics.py:437-441` 只断言容器类型与元素为 int，基线 `environment/workspace/wspawn/inherit.py:41` 的 `return []` 即可通过（参考解 `solution/reference/wspawn/inherit.py:74-83` 也只返回自记集合，并非「进程内所有可继承对象」）。
- 影响：假阴性（覆盖不足）——只修好 `set_inheritable`/`handle_kind`、`spawn` 仍「全给」的实现会通过 2 条 F2P 用例；`handle-handover` 分组实际只靠 `test_unlisted_handle_does_not_cross_the_boundary` 一条支撑。
- 修复方向：让这两条用例把泄漏对象的句柄值也交给子进程（或让子进程扫描父进程声明集合）后再比对，并让 `inheritable_handles()` 对套件自建的可继承句柄做交叉断言。

### C4 覆盖不足：题面要求 vs 实际用例
- 问题：题面 F 条错误分类与 E 条对象识别中的多类行为在隐藏套件里完全没有对应用例，而这些路径在 Windows 上可达。
- 证据：
  - `instruction.md:56`「相关接口必须抛出 `WSpawnError`，且 `err.kind == "unsupported"`」；隐藏套件只在 `tests/test_wspawn_semantics.py:403` 写 `assert exc.kind in ("os", "badarg", "unsupported")`，无任何断言排查 `unsupported`（`tests/` 内 grep `unsupported` 仅此一行）。
  - 该分类在验收环境可达：`solution/reference/wspawn/proc.py:111-116`（`stdout=subprocess.PIPE`）会产 `unsupported`，却无用例。
  - `instruction.md:51` 要求区分「文件、管道、控制台、无法识别」；`tests/test_wspawn_semantics.py:383-395` 只断言 `"pipe"`、`"file"`，console/unknown 分支无用例（可见冒烟 `tests/test_wspawn_basic.py:105` 也只做集合成员判断）。
  - `instruction.md:42`「对不支持该操作的对象，必须按 F 报错，不得静默返回」：隐藏套件无 `set_inheritable` 不支持路径用例，仅由可见冒烟 `tests/test_wspawn_basic.py:93-96` 间接覆盖（且只查 `kind in KINDS`）。
- 影响：覆盖不足（假阴性：`unsupported` 分类缺失、console/unknown 分类缺失的实现仍可满分；C 条「不得静默返回」无独立证据）。
- 修复方向：补 `stdout=subprocess.PIPE` 一类可达路径的 `unsupported` 断言，并补 console（如 `CONOUT$` 句柄）与不可识别对象的 `handle_kind` 用例。

### C8 基础设施故障被当成 0 分
- 问题：`collected == 0` 被无条件解释为「候选包无法导入」，14 条 required 全判 FAIL，链路输出 `run_validity=VALID` + `formal_score=0`；套件被截断/损坏、pytest 收集期内部错误等非候选原因同样落在这条路径。
- 证据：
  - `tests/run_tests.ps1:172-183`：`if ($collected -eq 0) { ... status = 'FAIL'; detail = 'the suite collected no case at all; the candidate package could not be imported' }`；前置检查 `:63-70` 只验证套件文件存在，不验证其内容可被收集。
  - `tests/aggregate_results.ps1:100-112`：全部 FAIL ⇒ `invalidTotal` 仍为 0 ⇒ `$runValidity='VALID'`、`$formalScore=0`。
  - `tests/test.ps1:64-77`：见到 `run_validity=VALID` 即写 `reward.txt`/`reward.json`/`reward-details.json` = `formal_score`，不触发 `===SWELIVE_INVALID===`；对照 `tests/run_tests.ps1:157-159`、`:209-212`，error/skip 与「部分收集」路径确实会 `exit 2`（漏洞仅限 `collected==0`）。
  - 12 次记录运行（`jobs/_index/assembly_report.json:1-110`）全部 `cases=14`，该分支从未被走到。
- 影响：假阳性（基础设施故障冒充候选人 0 分，同时掩盖环境故障）。
- 修复方向：仅在能证明「候选包不可导入」（如先单独 `python -c "import wspawn"`）时判 FAIL，其余 `collected==0` 标 INVALID 并 `exit 2`。

### C14 题面范围 vs 测试覆盖
- 问题：题面 E 条四类识别、F 条三类错误分类实际只覆盖 2 类识别 + 2 类分类（badarg/os 亦仅间接覆盖），「满分」不能支撑题面 A–G 全部成立。
- 证据：`instruction.md:51` 对照 `tests/test_wspawn_semantics.py:390-391`（只有 file/pipe）；`instruction.md:56` 对照 `:403`（三选一，等于无约束）；`instruction.md:63` 对照 `:437-441`（只查容器与元素类型，签名与语义无断言）。
- 影响：覆盖不足（题面结论被夸大：console、unknown、unsupported 三项无证据）。
- 修复方向：与 C4 同源，补齐 E/F 各类别用例后再宣称覆盖全部验收条款。

### C16 失败证据不完整
- 问题：结构化落盘记录只剩布尔值，逐 case 期望/实际值不在其中；pytest json 报告写在临时目录并被删除。
- 证据：
  - `tests/aggregate_results.ps1:101-104`：`[pscustomobject]@{ test_id = ...; passed = ($st -eq 'PASS') }`。
  - `jobs/ctl-nop-1/verifier/report.json:11-68`：14 条 cases 均只有 `test_id`/`passed`；`reward-details.json:179-250` 的 checks 明细里 `detail` 只有 `"pytest outcome=failed"`。
  - `tests/run_tests.ps1:103` 报告写入临时 `$runRoot`，`:217` finally 中 `Remove-Item -LiteralPath $runRoot -Recurse -Force`。
  - 缓解证据：`jobs/ctl-nop-1/verifier/test-stdout.txt:11-58`（`-rA --tb=short` 原文，含 `kind=3 ok=1 written=13 err=0`、`'unknown' == 'pipe'`）与 `jobs/ctl-nop-1/verifier/verifier.log:4-84` 保留同一份原文，失败项尚可逐条复核。
- 影响：覆盖/复核不足（仅凭包内 report/reward 三件套无法逐 case 复核实际值，须依赖平台另存 stdout）。
- 修复方向：把 pytest json 报告或逐 case 期望/实际值复制进 `results/` 随包保存。

## 待确认项说明

- C13：`instruction.md:17`「`set_inheritable()` 之后…没有任何变化」与冻结基线不符 —— 基线 `environment/workspace/wspawn/inherit.py:19-21` 对 Windows HANDLE 会抛 `os.set_inheritable` 的 `OSError`，实测落为 `WSpawnError(kind="os")`（`jobs/ctl-nop-1/verifier/test-stdout.txt:25`、`:32`）；`instruction.md:18`「句柄值对不上」也未复现 —— 基线是「全部继承」，被继承句柄数值并未错位（`test-stdout.txt:19` 显示子进程按父进程给的数值成功写入 `kind=3 ok=1`）。两条可勉强读作「调用方手上的值在子进程不可用」，且与 A–G 无冲突，故未判 FAIL；是否改写题面需人工判断。
- C17：包内无 `network_mode`/禁网声明（`environment/adapter.toml:27-34` 只有 engine/image/task_root/shell），`environment/Dockerfile` 只声明构建期离线；未发现指向上游补丁的可下载地址（`source.json:7-9` 是 Microsoft Learn 文档页，`:10` 明示未复制上游源码），6 条模型轨迹按 `pip install|git clone|curl|Invoke-WebRequest|https://github.com|socket` 检索零命中。运行时禁网与否需主流程核查。

## 未覆盖 / 不确定

1. 未逐行读：`jobs/*/job.log`、`jobs/*/trial.log`（仅按 `network|internet|proxy` 扫过）、`solution/solve.ps1`、`verifier/oracle/solve.ps1`（两者 sha256 不同，C6 归主流程）、`environment/cleanup.ps1`、`environment/vendor/INVENTORY.json`、`jobs/result.json`、`jobs/lock.json`、`jobs/model-*/agent/patch.diff` 与 `trajectory.jsonl`（仅关键词检索）。
2. C2 两处弱旁证（`is_inheritable` 须返回真 bool 才能过 `is True/is False`；`inheritable_handles()` 元素须为 int）在 `instruction.md` 无直写依据；若甲方按「题面直写」口径，应升格为 C2 问题。
3. C3 可利用性：套件实际只靠 `test_unlisted_handle_does_not_cross_the_boundary` 检出泄漏；「候选人把 `inherit` 之外的句柄改成无效值再交出」等更隐蔽绕过未评估（静态无法穷举）。
4. C16 判定依赖「平台会另存 verifier stdout」；若交付物只保留 verifier 目录三件套则视为彻底 FAIL（本批 `jobs/*/verifier/test-stdout.txt` 与 `verifier.log` 证明 stdout 确实被保存）。
5. 顺手观察（不计入判定，归主流程）：C18 —— `environment/Dockerfile:13` 为完整版 `windows/server:ltsc2022`（build 20348，版本不过旧），但运行镜像 `environment/adapter.toml:30`、`environment/agent_visible_paths.json:7` 为 `servercore:ltsc2022`，交付声明与运行镜像 flavor 不一致；C5 —— `f2p-empty-inherit-leaks-nothing` 与 `f2p-only-one-of-two-handed-over-pipes-crosses` 在 `ctl-nop-1..3` 三次空跑均 PASS（`jobs/ctl-nop-1/verifier/report.json:17-22`），7 条 F2P 里有 2 条并非真 F2P；C6 —— `jobs/_index/assembly_report.json:1-110` 显示 oracle×3=1、nop×3=0 且全 VALID、14/14 匹配，但 `verifier/README.md:25` 声称的 `verifier/evidence/verifier-run/` 在包内不存在；C9 —— opus 3×1、qwen 0/1/1（非双满双零）；C10 —— `jobs/model-opus-1/config.json:9` 为 `"claude-opus-5"`、`base_url=https://4router.net`；C11 —— 包内无 `jobs/invalid-slots.json`/`INVALID-SLOTS.md`，`jobs/job.log` 仅一行 `Skipping image OS validation ... docker inspect returned 1`。
