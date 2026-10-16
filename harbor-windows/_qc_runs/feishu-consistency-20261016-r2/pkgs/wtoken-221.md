包 wtoken-221：C 项结论概览（PASS 6 / FAIL 5 / 待确认 1）

范围说明：本次只做静态核对。题包内**没有 `jobs\` 目录**，因此凡需 jobs 记录（C5/C6/C9/C10/C11 及 C17 的轨迹部分）一律 N/A（包内无 jobs）。审查对象：`harbor-windows\wfflab__wtoken-221-v1.0.0-delivery`。

## 逐项结论

C1: PASS — 隐藏套件只 import 题面在 `instruction.md:66` 列出的 8 个公开符号，未触碰任何私有模块/函数（无 `_winapi`、无内部数据布局依赖） — 证据 tests\test_wtoken_semantics.py:33-43、instruction.md:66；附带瑕疵：第33行绑定的名字是 `wtoken_package`，第401行却 `globals().get("wtoken")`，该 fallback 分支为死代码（因 scratch 的 `tests\test_wtoken_basic.py` 命中第一候选，不产生影响）。

C2: FAIL — `integrity_level()` 的判分要求候选返回一组**题面从未给出**的固定词表（小写 `medium plus`/`protected process` 等），属题面外断言 — 证据见下。

C3: PASS — 所有关键断言都由评测器自持句柄独立观测（`observed_privileges/observed_enabled/observed_elevated`），不采信候选返回值；条件式 skip 与 fixture 缺候选全部映射成 INVALID 而非通过（run_tests.ps1:163-166、215-218），清理类断言与 cleanup.ps1:29 的 `wtoken-graded-*` 前缀一致（run_tests.ps1:75）。

C4: FAIL — 题面 E 的「提升类型」与题面 F 的「底层系统调用失败抛 `kind="os"`」两条可验收行为**完全无用例** — 证据见下（映射表）。

C7: PASS — 评分入口唯一：test.ps1 → run_tests.ps1 → aggregate_results.ps1（无第二个计分器）；`formal_score`（aggregate_results.ps1:111-112）与 `verdict`（:64-77、:127）都是「必过集合全过才 1」的二值规则，同输入不会分歧；`rubric.json` 实测 SHA256 = `c22a5293…fce03`，与 judge.toml:22 记录一致。

C8: FAIL — 「测试整体收集失败」这一基础设施路径会落到 VALID/0 而不是 INVALID — 证据见下。

C12: PASS — `instruction.md` 全文与本题任务和解收相关，无别的题的技术约定或模板段落；`docs/NOTES.md` 的不一致已由题面 instruction.md:23 显式标注为「早期草稿」并作废。观察（非题面）：tests\run_tests.ps1:3 仍写 "the wtoken space-management contract"（模板残留字样）。

C13: PASS — 题面五条现象与包内实现逐条吻合（`privileges.py:43` 全部报 True、`:16` 解析 `whoami /priv`、`:63`/`:76` 用行号充当标识、`:55` 抛 unsupported、`token.py:14-21` 用 `geteuid`）— instruction.md:15-19 与 environment\workspace\wtoken\privileges.py:16-76、token.py:14-28 一致，未发现事实错误或前后矛盾。观察（非题面）：source.json:12,14 称基础镜像为「Windows Server Core」，与 Dockerfile:14,31、task.toml:19 的「非 Server Core、ltsc2022」矛盾；verifier\oracle\README.md:22 称 ltsc2022 的 os.version 为 `10.0.26100`，与 Dockerfile:18（20348）矛盾。

C14: FAIL（与 C4 同一处证据，不重复放大） — 全部公开方法都有用例，唯一未被覆盖的具体行为是题面 E 的「提升类型」，因此满分不能支撑「elevation 反映真实提升类型」的整题结论 — 证据同 C4。

C15: PASS — 题面 instruction.md:11 显式声明「跨平台兼容…不在验收范围内」，不存在「要求 POSIX 行为不变却无回归验证」的情形。

C16: FAIL — 失败落盘只有布尔与 outcome 字符串，无逐 case 实际值/期望值/stdout/stderr，pytest 原始 JSON 报告随临时目录删除 — 证据见下。

C17: 待确认 — 包内没有任何禁网声明（task.toml、environment\adapter.toml 均无 network/network_mode 字段），无法证明评测容器禁网；亦无 jobs 轨迹可核对。Dockerfile:31 以 tag 引用基础镜像（作者在 :24-30 自认 pin digest 会强制联网），adapter.toml:30 改用 digest；environment\vendor\INVENTORY.json:4-6 记录了下游下载 URL（仅作为构建来源记录）。包内没有指向上游补丁的地址。

## FAIL 项明细

### C2 未公开的判分条件
- 问题：`integrity_level()` 必须精确等于隐藏套件内置的 7 项小写词表之一，该词表在候选可见处（instruction.md、workspace/README.md、docs/NOTES.md、`wtoken/__init__.py` docstring）均未出现。
- 证据：
  1. `tests\test_wtoken_semantics.py:166-174` — `INTEGRITY_RID_NAMES = {0x2000: "medium", 0x2100: "medium plus", 0x3000: "high", …}`
  2. `tests\test_wtoken_semantics.py:379` — `assert reported.strip().lower() == expected`
  3. `instruction.md:55` — 只写「必须返回令牌强制完整性级别的名称，而不是占位字符串」，无词表；env workspace\README.md:30、docs\NOTES.md:39-42 同样无词表
  4. 参考解用首字母大写（solution\reference\wtoken\_winapi.py:42-50），靠 `.lower()` 才与套件对齐 → 说明这是评测侧隐式约定
- 影响：假阴性（候选返回 Windows 惯用名如 `Medium Mandatory Level` 会被判错）
- 修复方向：把允许的完整性级别名称集合写进 instruction.md 验收标准 E。

**C2 断言 → 题面依据对照表**

| 测试断言（文件:行） | 题面依据 |
|---|---|
| 清单键集等于令牌（:245） | 有，instruction.md:29-30 |
| 持有但关闭的项报 False（:255） | 有，instruction.md:30、36 |
| 启用项报 True（:260） | 有，instruction.md:36 |
| 关闭仍算持有 has_privilege True（:268） | 有，instruction.md:35 |
| set_privilege 改动能被系统读到（:285、:294） | 有，instruction.md:41-42 |
| 未持有特权必须报错（:311-314） | 有，instruction.md:44、59-60 |
| privilege_luid 等于系统 LUID（:327） | 有，instruction.md:48 |
| name/luid 互逆（:334、:342） | 有，instruction.md:49 |
| 未知名/未知标识/非整数 → badarg（:348、354、360） | 有，instruction.md:50、60（非整数由 F「参数不可用」+ 可见冒烟测试 :58-61 覆盖） |
| elevation()["elevated"] 等于 TokenElevation（:368） | 有，instruction.md:54；键名由可见冒烟测试 tests\test_wtoken_basic.py:73 固定 |
| integrity 名称 == 内置小写词表（:379） | **无**（仅「返回名称」的模糊表述） |
| privileges() 值必须是 bool（:390） | 部分：instruction.md:29 只写「值是否启用」；bool 由可见冒烟测试 :28 固定 |

### C4 覆盖不足
- 问题：① 题面 E 要求「提升状态**与提升类型**」，测试只断言 `elevated`，`TokenElevationType` 常量声明后从未使用；文档层却声称已比较该字段。② 题面 F 要求底层系统调用失败抛 `kind="os"`，无任何故障注入用例，拒绝类用例反而放宽到三种 kind。
- 证据：
  1. `tests\test_wtoken_semantics.py:365-369` — 只 `assert state.get("elevated") is observed_elevated()`；`:55` `TokenElevationType = 18` 全文件无引用
  2. `tests\judge.toml:11`、`verifier\rubric.conditions.json:60` — 均声称「compares elevation against TokenElevation / TokenElevationType / TokenIntegrityLevel」
  3. `tests\test_wtoken_semantics.py:313-314` — `assert caught.value.kind in ("badarg", "unsupported", "os")`
  4. `instruction.md:54`、`instruction.md:60`
- 影响：假阴性（elevation 的 type 恒为占位符仍得满分）+ 覆盖不足（F 的 os 分类无验证）
- 修复方向：补 TokenElevationType 值比对用例，并为 F 增加一类系统调用失败的分类断言（或把判定放宽写进题面）。

**题面条款 → 用例映射（缺项标注）**

| 条款 | 用例 |
|---|---|
| A 清单完整/一致/不依赖外部命令 | test_inventory_matches_the_token_exactly、_marks_disabled/_marks_enabled；「不依赖外部命令」仅间接覆盖 |
| B 持有≠启用 | test_a_disabled_privilege_is_still_held、test_held_and_enabled_disagree_… |
| C 启停真实生效且外部可观测 | test_enabling_…、test_disabling_…、test_switching_round_trip_… |
| C 未持有须报错 | test_set_privilege_rejects_a_privilege_the_token_does_not_hold |
| D 名称/标识双向一致 | test_luid_matches_…、test_name_and_luid_are_inverses、test_privilege_name_round_trips_…、test_unknown_… |
| E 提升状态 | test_elevation_matches_the_token |
| E 提升类型 | **缺** |
| E 完整性级别 | test_integrity_level_names_the_token_level |
| F unsupported/badarg 分类 | test_unknown_…×3、test_set_privilege_rejects_… |
| F 系统调用失败 → kind="os" | **缺**（无故障注入） |
| G 冒烟不回归、公开 API 不变 | test_visible_smoke_suite_still_passes、test_privileges_returns_a_plain_mapping、test_has_privilege_returns_a_boolean_… |

### C8 基础设施故障被当成 0 分
- 问题：`run_tests.ps1` 未核实「收集为空」的原因，一旦 pytest 收集总数为 0（套件被改坏、conftest 冲突等评测侧/环境侧故障），它把 20 个必过项全部硬编码为 FAIL，聚合后 `invalid=0` → `run_validity=VALID` + `formal_score=0`。
- 证据：
  1. `tests\run_tests.ps1:169` — `$collected = @($doc.tests).Count`
  2. `tests\run_tests.ps1:183-189` — `if ($collected -eq 0) { … status = 'FAIL'; detail = 'the suite collected no case at all; the candidate package could not be imported' }`（注释把 collected=0 一律归因为候选包不可导入，但脚本只看了条数，未读报告里的 errors/collectors）
  3. `tests\aggregate_results.ps1:111-112` — `$runValidity = 'VALID'`、`$formalScore = 0`（此时 `invalidTotal=0`）
- 影响：假阴性（环境/套件故障被记成候选 0 分）
- 修复方向：collected=0 时区分「候选导入失败」与「套件/环境收集失败」，后者置 INVALID（exit 2）。

### C14 题面范围 vs 覆盖范围
- 问题/证据/影响/修复：同 C4①。此处仅声明「满分不足以支撑题面 E 的整题结论」，不重复计数。

### C16 失败证据完整性
- 问题：cases 只有 `test_id` + `passed`；落盘错误详情只有一个 outcome 字符串；pytest 的 `--json-report` 产物在临时目录被 finally 删除，交付物里无法逐一复核失败项的实际值。
- 证据：
  1. `tests\aggregate_results.ps1:101-104` — `[pscustomobject]@{ test_id = …; passed = ($st -eq 'PASS') }`
  2. `tests\run_tests.ps1:166` — `Detail = "pytest outcome=$outcome"`
  3. `tests\run_tests.ps1:223` — `Remove-Item -LiteralPath $runRoot -Recurse -Force`（pytest-results.json 随之删除）
- 影响：覆盖不足（人工无法复核失败项）；另需注意 pytest `--tb=short -rA` 输出只进 stdout/宿主日志
- 修复方向：把逐 case 的期望值/实际值/异常文本写入 cases[]，并将 pytest JSON 报告随结果落盘。

## 额外发现（超出 C 项，需单独决策）

1. **prepare 清单与实际工作区不符，会让走 prepare 的链路直接 INVALID**：environment\prepare.ps1:19-27 要求 `wtoken\proc.py`、`wtoken\inherit.py`、`wtoken\kinds.py`，而 environment\workspace\wtoken 下实际只有 `errors.py / privileges.py / token.py / _winapi.py / __init__.py`（全包文件枚举确认）。prepare 必然 `exit 1`；environment\run.ps1:22-23 把非零转成 `exit 2`（INVALID）；task.toml:49 又把 `environment/prepare.ps1` 作为 setup。倾向：环境准备失败，而非候选 0 分。
2. tests\required_testcases.json:36、:80 把两项 `p2p-` 前缀用例的 group 标成 F2P，与 tests\judge.toml:13「F2P 8 / P2P 12」口径不符（实为 F2P 10 / P2P 10）。该文件不参与计分（计分只读 rubric.json），仅影响 F2P 声明。
3. 记录类文档与实物不一致：verifier\oracle\README.md:22（build 26100）、source.json:12,14（Server Core）、environment\adapter.toml:42,59 列出的 `workspace\assets` 目录并不存在（无害冗余）。
4. 正向确认：两份隐藏套件字节一致（SHA256 `B71E344B8176…7FC498`，tests\ 与 verifier\tests\ 各一份），满足 verifier\README.md:16-20 的要求。

## 未覆盖/不确定

- C17：包内无 network_mode/禁网声明，也未随包提供 jobs 轨迹；「评测容器是否禁网」无法在静态范围内判定。需人工核对 Harbor 侧网络策略与 Dockerfile:31（tag 引用）在离线导入镜像前提下的实际行为。
- C5/C6/C9/C10/C11/C18 按分工未展开；其中 C5 所依赖的 F2P 空跑基线因无 `jobs\` 记录为 N/A（包内无 jobs）。
- tests\required_testcases.json 的 group 语义是否被外部 reviewer 采用，包内无消费者代码可证。
- 未运行任何测试/容器，因此 C4 缺口的「是否真的会漏判」与 fixture 是否总能找到「关闭的持有特权」（tests\test_wtoken_semantics.py:219-221、234-237 的 skip 路径）均基于静态阅读判断。
