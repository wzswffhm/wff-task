# wfflab__wvas-216 静态质检结论

包 wvas-216：C 项结论概览（PASS 4 / FAIL 7 / 待确认 0；另 C15 判 N/A）

C1: PASS — 隐藏测试只 `import wvas` 并用题面公开入口（regions / modules / file_backed_regions / WVasError），无私有符号引用 — tests/test_wvas_semantics.py:43,292,383,425,48
C2: FAIL — 隐含断言「modules() 每条 path 必须是 str」，与题面「path 允许为 None」相反 — tests/test_wvas_semantics.py:385 vs instruction.md:76-77
C3: FAIL — 区间断言只比最高 base 与定点覆盖，不比对区间集合，可被「少报区间/夸大 size」绕过 — tests/test_wvas_semantics.py:296-301,310-317,153-157
C4: FAIL — 题面 B.4 顺序、C 完整性与 path、D 三个错误 kind、E.3 依赖联网均无用例 — instruction.md:69-71,76-77,87-89,97
C7: FAIL — 声明层加权 rubric 与实现层二值计分口径不一致，同一输入可得 0.62 或 0 — tests/rubric.json:7-80 vs tests/aggregate_results.ps1:101-102
C8: FAIL — fixture 阶段的环境失败被记为候选 FAIL，产出 VALID/0 — tests/run_tests.ps1:155；tests/test_wvas_semantics.py:274-277
C12: PASS — 题面通篇围绕本题验收，无别题约定或模板残留 — instruction.md:1-109
C13: FAIL — 现象 2 与现象 3 自相矛盾；C 节「path 可为 None」与 E.2 必过冒烟用例互斥 — instruction.md:20-24,76-77,95-96
C14: FAIL — 题面要求整包「完全正确」，而 modules 路径正确性、清单完整性、三种错误分类无用例，满分不能支撑题面结论 — instruction.md:8,74-77,87-89
C15: N/A — 题面明确排除其他操作系统，不存在跨平台不变量要求 — instruction.md:10；environment/workspace/README.md:46
C16: PASS — 失败项可逐一复核：保留完整 pytest -rA/--tb=short 输出（期望值、实际值、异常原文）与逐 case 状态 — jobs/ctl-nop-1/verifier/test-stdout.txt:15,20,51
C17: PASS — 构建与判分全离线（vendored + `pip --no-index`），题面无下载地址，agent 轨迹无外网取源码证据 — environment/Dockerfile:26-53；instruction.md:97

---

## C2 未公开/冲突的判分条件

- 问题：`f2p-modules-are-deduplicated` 直接对每条 `path` 调用 `os.path.normcase`，无 None 保护，等价于断言「modules() 不得返回 path=None 的映像」；题面 C 节却写明这类映像「仍然必须出现，它的 `path` 允许为 `None`」。
- 证据：
  - `tests/test_wvas_semantics.py:385` — `paths = [os.path.normcase(item["path"]) for item in modules]`
  - `instruction.md:76-77` — 「…如果某个映像的文件路径无法还原成调用方可直接打开的形式，该映像仍然必须出现，它的 `path` 允许为 `None`。」
  - `jobs/model-qwen-3/verifier/test-stdout.txt:25` — `TypeError: expected str, bytes or os.PathLike object, not NoneType`（该 F2P 因此判 FAIL）
- 影响：假阴性（按题面合法返回 None 即失分，已实际触发）。
- 修复方向：测试改为 `item["path"] or ""`，并把「完整性」写成显式断言。

### 断言 → 题面依据对照

| 测试断言 | 题面依据 |
|---|---|
| `max(base)` 相等且至少一个 > 4 GiB（:296-304） | 有（instruction.md:51,61-62） |
| 6 GiB 保留区被覆盖且 `size >= reserve_size`（:310-317） | 有（instruction.md:52） |
| 覆盖点 `state == "reserve"`（:325） | 有（instruction.md:53,59） |
| `normcase(path)` 等于样本路径且文件存在（:342-345） | 有（instruction.md:66-67） |
| 非空 path 不带 `\Device\`/`\??\`/`\\?\`（:355-357） | 有（instruction.md:66） |
| 匿名映射 `path is None`（:367） | 有（instruction.md:68） |
| `kind == "no-such-process"`（:376） | 有（instruction.md:86） |
| modules 去重（:386） | 有（instruction.md:74），但隐含 path 必须为 str → **题面外且相反** |

---

## C3 断言缺口 / 可被绕过

- 问题：整套区间类 F2P 只有「最大值相等」与「定点覆盖」两类核对，从不把候选报出的区间与测试自测的 `_observed_regions()` 逐条比对，也不核对条数或覆盖率。只回报 5–6 个构造区间（覆盖最高 base、6 GiB 保留段、文件映射、匿名映射）即可通过全部 16 项；`size` 只受下界约束，可任意夸大。题面却要求「`base`/`size` 必须与系统 API 量到的结果逐个一致」。
- 证据：
  - `tests/test_wvas_semantics.py:296-301` — 只比较 `max(item["base"])`，未比对集合
  - `tests/test_wvas_semantics.py:314-316` — `assert region["size"] >= target["reserve_size"]`（下界而非相等）
  - `tests/test_wvas_semantics.py:153-157` — `_covering()` 只返回第一个覆盖该地址的区间
  - `instruction.md:61-62` — 「…必须与系统 API（如 `VirtualQueryEx`）量到的结果逐个一致」
- 影响：假阳性（少报、夸大 size 仍可满分）。
- 修复方向：将 `_observed_regions()` 结果与候选结果逐条比对（条数 + 逐区间 base/size/state）。

---

## C4 覆盖不足：题面条款 vs 实际用例

- 问题：题面多条可验收行为无用例，缺项集中在文件映射路径与错误分类。映射表（缺项见「结论」）：

| 题面条款 | 对应用例 | 结论 |
|---|---|---|
| A `base`/`size` 与系统 API 逐个一致（instruction.md:61-62） | tests:290-304,307-317 | 缺「逐个」 |
| A `include_reserved` 两种语义（instruction.md:59） | tests:320-330,433-437 | 覆盖 |
| B.1/B.2 可打开且真实的磁盘路径（instruction.md:66-67） | tests:333-345,348-357 | 覆盖（仅 regions） |
| B.3 无文件背衬为 `None`（instruction.md:68） | tests:360-369 | 覆盖 |
| B.4 `file_backed_regions` 顺序与 `regions` 一致（instruction.md:69-71） | tests:422-430 | **缺顺序** |
| C 清单完整、path 为真实磁盘路径（instruction.md:74-77） | tests:381-388 | **缺完整性、缺 path 校验** |
| D `access-denied`/`unsupported`/`query-failed`（instruction.md:87-89） | 无 | **缺** |
| E.1 纯函数语义（instruction.md:93-94） | tests:454-465 → test_wvas_basic.py:70-75 | 间接覆盖 |
| E.3 无第三方依赖、不得联网（instruction.md:97） | 无 | **缺** |

- 影响：覆盖不足（题面承诺的验收面大于实际判分面）。
- 修复方向：补 modules 路径与完整性用例、`file_backed_regions` 顺序断言、三个错误 kind 的构造用例。

---

## C7 评分入口与规则一致性

- 问题：可执行计分链路只有 `test.ps1 → run_tests.ps1 → aggregate_results.ps1` 一条且规则一致（二值）；但包内另以 `rubric.json` + `judge.toml` 声明 7 组加权 rubric，并被 judge.toml 指为 authoritative_source。按声明口径与实现口径会得到不同分数，且 `_index` 下两份汇总互相矛盾。
- 证据：
  - `tests/rubric.json:7-80` — 7 组权重 0.18/0.12/0.22/0.10/0.10/0.10/0.18，`total_weight: 1.0`
  - `tests/judge.toml:19-22` — `authoritative_source = "rubric.json"`、`programmatic_weight = 1.0`
  - `tests/aggregate_results.ps1:101-102` — `scheme = 'binary-required-testcases'`、`weights = $null`
  - 同一输入 `model-qwen-3`（13/16，失败项属 error-classification 0.10、module-inventory 0.10、api-and-regression 0.18）：aggregate 得 0（jobs/model-qwen-3/verifier/report.json:10），rubric 加权得 0.62
  - `jobs/_index/qualification_summary.json:224-235` 记 `model-qwen-1` reward "1"，实际 `jobs/model-qwen-1/verifier/reward.json` 为 `{"reward":0}`（`jobs/_index/assembly_report.json:84-92` 记 0）
- 影响：分数口径不一致（同一输入得 0 或比例分），汇总记录不自洽。
- 修复方向：明确以二值 aggregate 为唯一口径，并同步修正 rubric/judge 声明与 `_index` 记录。

---

## C8 基础设施故障被判成 0 分

- 问题：`run_tests.ps1` 只把 `passed`/`xpassed` 视为 PASS，其余（含 pytest 的 error、skipped）一律 FAIL；`aggregate_results.ps1` 只在「用例根本没被收集」时算 INVALID。于是隐藏测试 fixture 报出的环境问题（无法保留 6 GiB、target 起不来、无法建映射）会被算成候选失败，产出 `run_validity=VALID` + `formal_score=0`。12 轮记录未触发该路径，属静态判定。
- 证据：
  - `tests/run_tests.ps1:155` — `$status = if ($outcome -eq 'passed' -or $outcome -eq 'xpassed') { 'PASS' } else { 'FAIL' }`
  - `tests/test_wvas_semantics.py:274-277` — `pytest.fail("the fixture could not reserve 6 GiB of address space")` / `("the fixture could not create its mappings")`
  - `tests/aggregate_results.ps1:75` — `$runValidity = if ($casesTotal -gt 0 -and $invalidTotal -eq 0) { 'VALID' } else { 'INVALID' }`
- 影响：假阴性（环境缺陷被记成候选 0 分）。
- 修复方向：把 fixture/setup 阶段失败与 skip 映射为 INVALID，不要落到 FAIL。

---

## C13 题面描述不准确 / 自相矛盾

- 问题一：现象 2 称 6 GiB 保留段「报出来的长度是个很小的数」，现象 3 又称保留区间「结果里都不会出现」，两者不能同时成立；实测未修复包在该点的失败信息是「缺失」。
  - 证据：`instruction.md:20-21`；`instruction.md:22-24`；`jobs/ctl-nop-1/verifier/test-stdout.txt:20` — `the 6 GiB reservation at 0x1391a230000 is missing from the report`
- 问题二：C 节允许 `modules()` 的映像 `path` 为 `None`，E.2 又要求 `C:\testbed\tests\test_wvas_basic.py` 全部通过且不得修改，而该冒烟用例第 59 行断言 `assert item["path"]`；容器内映像经 VSMB 映射无法还原时，两条要求互斥（隐藏测试 :385 亦在 None 上崩溃）。
  - 证据：`instruction.md:76-77`；`instruction.md:95-96`；`environment/workspace/tests/test_wvas_basic.py:59`；`jobs/model-qwen-3/verifier/test-stdout.txt:39-40`
- 影响：假阴性（按题面「path 允许 None」实现会被隐藏用例与冒烟用例同时判失败）；参考解只能以丢弃映像规避 — `solution/reference/wvas/vas.py:236-238`，与题面「仍然必须出现」冲突。
- 修复方向：改正现象 2 措辞，并统一 C 节与冒烟用例对 `path=None` 的处理。

---

## C14 题面范围 vs 测试覆盖范围

- 问题：题面把整包结论抬到「要么完全正确，要么毫无用处」，并要求模块清单完整、`path` 为真实磁盘路径、五种错误 kind 全覆盖；16 个用例对 `modules()` 只验去重与排序，对错误分类只验 `badarg` 与 `no-such-process`，`file_backed_regions` 只验子集。16/16 不能支撑题面宣称的正确性。
- 证据：`instruction.md:8`；`instruction.md:74-77`；`instruction.md:87-89`；`tests/test_wvas_semantics.py:381-388,422-430`
- 影响：覆盖不足（满分结论被夸大）。
- 修复方向：与 C4 一并补用例；无法覆盖时收缩题面结论措辞。

---

## 未覆盖/不确定

1. 容器运行时是否禁网无法从包内核实：包内无网络策略字段；`source.json:7-9` 含 psutil 仓库与 4 个 issue URL，但 `environment/Dockerfile:59` 只 `COPY workspace/`，该文件不在 agent 可见面，也不含本题答案。
2. C8 缺运行实证：12 轮全部 VALID，未出现 fixture 失败实例；结论系静态代码路径判定，pytest-json-report 对 fixture error 的 `outcome` 取值未实证（`tests/run_tests.ps1:192` 删除暂存目录，pytest-results.json 不落盘）。
3. 包内汇总记录矛盾，未展开：`jobs/_index/qualification_summary.json:224-235` 与 `jobs/INVALID-SLOTS.md:24` 记 `model-qwen-1` reward 为 1（实际 0）；`model-qwen-3` 通过数在 `qualification_summary.json:251-258` 记 14、在 `jobs/model-qwen-3/verifier/result.json:8-9` 记 13。Opus/Qwen 区分度结论不变（3 > 1）。
4. `environment/adapter.toml:30` 本地 runner 镜像为 `windows/servercore:ltsc2022`，与 `environment/Dockerfile:21` 的 `windows/server:ltsc2022` 形态不同（build 均 20348）；C18 由主流程判定，此处仅记录。
5. `environment/cleanup.ps1:31` 残留检查只按固定前缀（`wvas-graded-*`、`wvas-target*`、`pytest-of-*`）枚举，属 C3 同族观察；该脚本不参与评分链路，未计入判定。
6. C5、C6、C9、C10、C11、C18 未展开（主流程统一处理）。
