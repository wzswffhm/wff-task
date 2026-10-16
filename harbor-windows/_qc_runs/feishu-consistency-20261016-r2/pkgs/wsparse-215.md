包 `wfflab__wsparse-215-v1.0.0-delivery`：C 项结论概览（PASS 5 / FAIL 4 / 待确认 2 / N/A 1）

C1: PASS — 隐藏套件只导入题面公开的 6 个入口，无私有符号/子模块/内部布局引用 — 证据 `tests/test_wsparse_semantics.py:31-38`、`instruction.md:67`
C2: PASS — 每条断言都能追到题面验收条款，或追到候选可见面（源码 docstring / README / 可见冒烟测试）；题面未直写的三处见下表 — 证据 `tests/test_wsparse_semantics.py:406-431`、`environment/workspace/wsparse/alloc.py:39`
C3: 待确认 — 两条 F2P 的关键断言全部只比较候选自报的 `allocated_ranges()`（套件自测值取了却未参与比对），形式缺口成立；但盲式谎报需先知道 fixture 偏移，静态无法确证可利用 — 证据 `tests/test_wsparse_semantics.py:295-312`、`:329-339`（`:331` 测得未比）
C4: FAIL — 题面 D 条「非稀疏文件返回覆盖整个长度的一个区间」与 F 条「相关接口（含 preallocate/sparse_flag）对目录必须抛 unsupported」无对应用例 — 证据 `instruction.md:53`、`:61`、`tests/test_wsparse_semantics.py:442-454`、`:379-388`
C7: PASS — 评分入口唯一（`task.toml` / `adapter.toml` 均指向 `tests/test.ps1`），`run_tests.ps1` 只写 checks 不打分，`aggregate_results.ps1` 的 `formal_score` 与 `verdict` 均为「全过才 1，否则 0」 — 证据 `task.toml:46`、`tests/aggregate_results.ps1:112`、`:127`
C8: FAIL — 套件一个用例都没收集到（`collected == 0`）时把 20 条 required 全判 FAIL，链路最终产出 `run_validity=VALID` + `formal_score=0` — 证据 `tests/run_tests.ps1:183-189`、`tests/aggregate_results.ps1:100-112`
C12: PASS — `instruction.md` 全文 71 行都是本题 NTFS/稀疏语义内容，无模板残留、无别题技术约定（关键词 grep 无命中） — 证据 `instruction.md:1-71`
C13: FAIL — 现象 4 把「补设稀疏标志后占用没降」当缺陷，验收 E 条却要求占用必须不降；现象 1 称同一行代码在 Linux 上「几乎不占空间」，与包内写零实现矛盾 — 证据 `instruction.md:22`、`:57`、`:19`、`environment/workspace/wsparse/alloc.py:47-56`
C14: PASS — 题面要求的行为集合与 20 条用例大体对应，无「只测一个函数却宣称整个子系统合规」的夸大；缺口与 C4 同源，已在 C4 记录 — 证据 `tests/rubric.json:7-77`
C15: N/A — 题面明确声明不验收其他平台、也不要求实现其他平台版本，故不存在「跨平台不回退」要求与验证缺失 — 证据 `instruction.md:11`、`:15`、`tests/test_wsparse_semantics.py:25-29`
C16: FAIL — 落盘的 `cases[]` 只有 `test_id`+`passed`；pytest json 报告写在临时目录并在 finally 删除，未随包保存 — 证据 `tests/aggregate_results.ps1:101-104`、`jobs/ctl-oracle-1/verifier/report.json:11-92`、`tests/run_tests.ps1:103`、`:223`
C17: 待确认 — 包内没有任何禁网/放网声明（adapter 无 network 配置），轨迹里只出现 LLM 端点、无取上游源码或补丁的痕迹；运行时是否禁网需主流程核查 — 证据 `environment/adapter.toml:27-34`、`jobs/model-opus-1/agent/model-result.json:6`

## C2 对照表（测试断言 → 题面依据）

| 隐藏套件断言 | 题面依据 |
|---|---|
| 稀疏位置位、长度=size、1 GiB 实测 < 8 MiB、幂等（`tests/test_wsparse_semantics.py:276-293`、`:412-416`） | 有：`instruction.md:31-35` |
| 写入后只分配写入过的区域（`:295-312`） | 有：`instruction.md:37-41`、`:49-53` |
| `disk_usage` 与系统实测差 ≤ 64 KiB（`:317-324`） | 有：`instruction.md:43-47`（±64 KiB 容差是测试自设，宽松） |
| 区间升序/不重叠/界内/全空洞为空/空文件为空（`:329-344`、`:442-460`） | 有：`instruction.md:49-53` |
| 密集文件补设标志后不得释放已分配簇（`:360-374`） | 有：`instruction.md:55-57` |
| 目录 → `WSParseError(kind="unsupported")`（`:379-388`） | 有：`instruction.md:59-62` |
| `kind == "badarg"`（负值/非整数，`:428-431`） | 题面无该串；候选可见面有：`environment/workspace/wsparse/errors.py:20`、`README.md:22`、可见冒烟测试 `tests/test_wsparse_basic.py:55-66`（题面 G 条要求其继续通过） |
| `preallocate` 返回长度、不得缩小（`:406-409`、`:419-425`） | 题面无；候选可见面有：`environment/workspace/wsparse/alloc.py:39` docstring、可见冒烟测试 `:30-52` |
| `sparse_flag(path, True)` 返回 `True`（`:349-357`） | 题面无；候选可见面有：`environment/workspace/wsparse/flags.py:23` docstring |
| `sparse_state`/`disk_usage` 返回类型（`:434-439`、`:463-466`） | 题面无；候选可见面有：可见冒烟测试 `:81-86`、`:116-119` |

## FAIL 项明细

### C4 覆盖不足
- 问题：题面 D 条要求「非稀疏文件返回覆盖整个长度的一个区间」，F 条要求「相关接口」在拿到目录时必须抛 `WSParseError(kind="unsupported")`；测试对这两条只做了部分覆盖。
- 证据：
  - `instruction.md:53`「全空洞文件返回空列表；非稀疏文件返回覆盖整个长度的一个区间」
  - `tests/test_wsparse_semantics.py:445-454` dense 用例只断言 `ranges` 非空、升序、不重叠、界内，未断言覆盖整个长度、也未断言是单一区间（返回 `[(0, 4096)]` 亦可过）
  - `instruction.md:61`「相关接口必须抛出 `WSParseError`」/ `tests/test_wsparse_semantics.py:379-388` 只测了 `disk_usage` 与 `allocated_ranges` 对目录；参考解 `solution/reference/wsparse/alloc.py:26-32`、`flags.py:34-39` 里 `preallocate`/`sparse_flag` 的目录分支无用例
- 影响：覆盖不足（假阴性：dense 下漏报区间、对目录直接抛裸 `OSError` 的实现仍可满分）
- 修复方向：补 dense「单一区间且覆盖整个长度」断言，并补 `preallocate`/`sparse_flag` 对目录的 `unsupported` 用例。

### C8 基础设施故障被当成 0 分
- 问题：`collected == 0` 被无条件解释为「候选包无法导入」，于是 20 条 required 全部标 FAIL，整条链路输出 VALID/0；平台守卫跳过、收集期环境异常等非候选原因同样落在这条路径上。
- 证据：
  - `tests/run_tests.ps1:183-189`：`if ($collected -eq 0) { ... status = 'FAIL'; detail = 'the suite collected no case at all; the candidate package could not be imported' }`
  - `tests/aggregate_results.ps1:111-112`：`$runValidity = if ($casesTotal -gt 0 -and $invalidTotal -eq 0) { 'VALID' } else { 'INVALID' }` / `$formalScore = if ($casesTotal -gt 0 -and $casesPassed -eq $casesTotal) { 1 } else { 0 }`；`tests/test.ps1:64-82` 见 `run_validity=VALID` 即写 `reward.txt`/`reward.json` = `formal_score`
  - 佐证：`verifier/ISOLATION.md:35-37` 声称缺失套件「never silently reported as a failed candidate」，代码只覆盖了「候选包缺失 / 套件未注入」两条 `exit 2` 路径
  - 同类：`tests/test_wsparse_semantics.py:204-216` 在 `fsutil` 不可用或输出无法解析时返回 `"unknown"`，`:281` 随即断言失败，验证器自身工具故障被算作候选失败
- 影响：假阴性（基础设施故障产出 VALID/0 冒充候选 0 分，同时掩盖环境故障）
- 修复方向：只有能证明「候选包不可导入」时才判 FAIL，其余 `collected==0` 标 INVALID 并 `exit 2`；把 `fsutil` 观测失败也改为 INVALID。

### C13 题面描述不准确
- 问题：对「补设稀疏标志后占用不降」这一同一行为，题面现象与验收条款给出相反的价值判断；另有一处与包内实现矛盾的行为陈述。
- 证据：
  - `instruction.md:22`「`sparse_flag(path, True)` 对一个已经扩展成密集的文件返回成功，但磁盘占用一点没降下来」（列为缺陷）
  - `instruction.md:57`「不得谎报成功：此时 `disk_usage()` 必须仍然反映真实的密集占用」，而 `tests/test_wsparse_semantics.py:368-374` 要求 `sparse_state(...) is True` 且 `after >= 16*MB`（即标志必须真的设上、占用必须不降）
  - `instruction.md:19`「同样一行代码在 Linux 上瞬间返回、几乎不占空间」与 `environment/workspace/wsparse/alloc.py:47-56`（1 MiB 零块循环写满尾部、无平台分支）矛盾：同一实现换到 Linux 同样写满、同样慢
  - 附带：`instruction.md:13`「评测器运行在 Windows Server Core 容器中」与 `environment/Dockerfile:20` 的 `windows/server:ltsc2022`（完整版）不一致，但与 `environment/adapter.toml:30` 的 `servercore:ltsc2022` 一致
- 影响：假阴性（候选可能为「不谎报成功」而让 `sparse_flag` 返回 False 或主动释放簇，反而挂掉 F2P `late-sparse-flag-does-not-free-clusters`）
- 修复方向：改写现象 4 与 E 条，明确「返回最终属性状态、置位不回收已分配簇」，并删掉或改写 Linux 对比句。

### C16 失败证据不完整
- 问题：包内落盘的失败记录只剩布尔值，逐 case 的期望/实际值依赖临时目录里的 pytest 报告，而该报告被删除。
- 证据：
  - `tests/aggregate_results.ps1:101-104`：`[pscustomobject]@{ test_id = ...; passed = ($st -eq 'PASS') }`
  - `jobs/ctl-oracle-1/verifier/report.json:11-92`：20 条 cases 均只有 `test_id` / `passed`
  - `tests/run_tests.ps1:103` 报告写入临时 `$runRoot`，`:223` finally 中 `Remove-Item -LiteralPath $runRoot -Recurse -Force`，pytest json 报告不随包保存
  - 缓解证据：`tests/test.ps1:150` 把带 `detail` 的 checks 嵌进 result.json；`jobs/model-qwen-2/verifier/test-stdout.txt:13-15` 保留了 `--tb=short` 的失败断言原文与 `DID NOT RAISE` 实际行为
- 影响：覆盖/复核不足（仅凭包内 result.json 无法逐 case 复核实际值，须依赖平台另存的 stdout）
- 修复方向：把 pytest json 报告或逐 case 的期望/实际值复制进 results/ 随包保存。

## 未覆盖 / 不确定

1. C17 运行时网络策略：包内无 `network_mode` / 禁网声明（`environment/adapter.toml:27-34` 只有 engine/image/task_root 等），Dockerfile 只声明构建期离线；运行时是否禁网无法静态判定，需主流程核查。`source.json:9-10` 含上游 issue URL 与修复要点，但该文件不在 agent 可见面（`environment/agent_visible_paths.json:11-55`、`environment/adapter.toml:41`），且 `jobs/model-*/agent/trajectory.jsonl` 的关键词 grep 只命中 LLM `base_url`。
2. C3 可利用性：形式缺口需「隐藏套件泄漏」前提才能被硬编码穿过，静态无法确证，故记待确认而非 FAIL。
3. 未逐行读：`jobs/*/job.log`、`jobs/*/agent/trajectory.jsonl`（仅关键词 grep）、`jobs/result.json`、`solution/solve.ps1`、`verifier/oracle/solve.ps1`、`environment/vendor/INVENTORY.json`、`environment/workspace/pyproject.toml`、`tests/test_wsparse_basic.py` 之外的可见面文件。
4. 顺手观察（不计入上述判定）：C18 镜像来源矛盾 —— `environment/Dockerfile:20` 为完整版 `windows/server:ltsc2022`，而实际运行镜像 `environment/adapter.toml:30`、`environment/agent_visible_paths.json:7` 为 `servercore:ltsc2022`；C5 —— `jobs/ctl-nop-1/verifier/report.json` 恰为 10 条 P2P 全 PASS、10 条 F2P 全 FAIL（`VALID/0`）；C6 —— `jobs/_index/assembly_report.json:1-110` 有 oracle×3=1、nop×3=0 且均 VALID，`verifier/evidence/` 只有 `golden`、`no_change`（`verifier/README.md:25` 写的 `evidence/verifier-run/` 与实际目录名不符）；C9 —— opus 3×1、qwen 1/0/0，非双满双零；C10 —— `jobs/model-opus-1/config.json:9` 为 `"claude-opus-5"`、`jobs/model-qwen-1/config.json:9` 为 `"qwen3.8-max-0902"`；C11 —— 包内无 `jobs/invalid-slots.json`。
