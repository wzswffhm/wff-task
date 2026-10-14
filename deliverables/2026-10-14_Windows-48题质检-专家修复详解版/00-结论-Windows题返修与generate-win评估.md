# Windows 题返修：generate-win 评估 + 同行 Windows 机制实现手法

> 产出日期：2026-10-14　｜　分析对象：
> 1. 飞书 wff 表三条返修原因（实测拉取，见 `harbor-windows/_qc_runs/windows-mechanism-rework/返修原因-三条-20261014.md`）
> 2. `C:\Users\Administrator\Desktop\generate-win.zip`（全文解压于 `deliverables/2026-10-14_generate-win/`）
> 3. 甲方《Windows-48题质检-专家修复详解版-20261012》
>
> 附件（同级 `notes/`）：
> - `A-019-036-021-Windows机制绑定.md`（019/036/021 三题逐层分析 + 可复用检查清单）
> - `B-NTFS系列-Windows机制绑定.md`（031/007/017/024/037 五题 + 对抗性夹具设计）
> - `C-进程IPC注册表-Windows机制绑定.md`（002.1/002.2/002.6/003/018/020/040/043 八题 + 三层锁定方法论）

---

## 一、先给结论

| 问题 | 结论 |
|---|---|
| 当前 skill 为什么**完全不满足** Windows 题要求？ | 不是没写规则，而是**规则没有变成门禁、也没有变成证据**。`references/02-windows-value.md` 的反事实判据写得完整，但 ① 只要求产出一个 `labels.json`；② `scripts/validate_package.py` **零条** Windows 价值检查；③ 更致命的是 215/216/218 包内 `verifier/WINDOWS_VALUE.md` **自己写"不主张 Windows 反事实价值、按通用编码能力归类"**——这句自认把定性钉死，甲方直接引为不合格证据。 |
| 改用 `generate-win` 能否满足？ | **不能整包替换**。它的**选题路线**对"依赖 Windows 机制"这一条有实质帮助（我们自己的 `wfflab__wreparse-217` 就是这条路线的产物，且被甲方评为 Windows 价值高的同类题材）；但它在**Windows 价值门禁、参考解交付口径、job 归档协议、INVALID/FAIL 语义、模型矩阵规则**这五项上要么缺失、要么与甲方现行规则相反。**实测**：拿甲方最新 `validate_model_jobs.py` 跑 217 的 `jobs/`，**20 条错误、pass=False**。 |
| 同行怎么做出"满足 Windows 题"的？ | 43 条被评估的题里 **37 条 Windows 价值高、8 条中等、仅 3 条低**（低的三条正是我们的 216、215 和另一个供应商的 directory-marker）。他们的公式是**三层锁定**：题面把机制名写进可验收行为 → 环境用真对象做能力探针且不满足即 INVALID → 验证器**自己持有内核对象**再观测候选是否操作了同一个对象。 |

---

## 二、三条返修原因与六条硬要求

飞书 wff 名下 4 条记录，其中 **216 / 215 / 218 三条带返修原因**（219 无返修原因）。去重后是六条要求：

| # | 要求 | 涉及 | 性质 |
|---|---|---|---|
| R1 | 交付**可独立验收**的参考解与隐藏测试（`solution/reference/*`、隐藏语义测试），并与模型隔离 | 215/216 | 缺件 |
| R2 | 冻结新版 Task 后**整批重跑**，job 的 `task_checksum` 必须绑定当前交付包 | 215/216 | 身份 |
| R3 | `required_testcases.json` 集合与 job 内日志/用例集合一致；补 GLM/Kimi 原始 job | 215/216 | 一致性 |
| R4 | 日志事实与飞书字段一致（Kimi 实际 1/1 vs 填 0/1；Opus 实得 2/3 vs 填 3/3） | 215/216 | 记录 |
| **R5** | **题目必须依赖 Windows 专属机制**，或按真实采购分类移出 Windows 池；**不得只改题名/标签** | 215/216/218 | ★ 核心 |
| R6 | `run_tests.ps1` 必须区分 **INVALID（缺测/执行故障）与 FAIL（功能失败）**，INVALID 不得输出正式 0 分 | 215/216 | 判分语义 |

专家给的修复路径原文（报告 ZQ004-03 / ZQ005-03）：

> 1. 把题目要求映射到真正依赖的操作系统机制
> 2. 若保留通用题，明确归入通用编码能力并调整采购分类
> 3. **若需要 Windows 专属评测，新增有实际产品需求的 Windows 语义，发布新版后重新作答**

第 3 条就是本轮的必答题。而 `harbor-windows/_index/CHANGELOG.md`（2026-10-12 条目）已白纸黑字记着：

> **Windows 专属化改造未实施**；如需 Windows 专属评测须立项发新版并重新作答。

即：这一条**从未做过**，不是做错了。

---

## 三、`generate-win` 逐条评估

`generate-win` 的实际内容：`SKILL.md`（241 行）+ 5 个 `references/` + 6 个 `scripts/`，其中 `scripts/validate_requirement_conformance.py`（302 行）是它唯一的自动化校验入口。

### 3.1 它强在哪：选题路线天然贴合 R5

`SKILL.md:81` 的选题要求是：

> Choose a real, reproducible **Windows-specific** coding problem from a public repository. Prefer a bounded production-code defect with deterministic automated verification.

它把"从真实上游项目选 Windows 专属缺陷"写成第一步硬要求，并配套了"先在飞书作业表查重"（`scripts/inspect_homework_table.ps1`）。**这条路线的产物天然带 Windows 机制**，因为缺陷本身长在 Windows 代码分支上。

**实证**：我们自己的 `wfflab__wreparse-217`（v1.3.0，通过甲方 QC 30 项、Opus 3 > Qwen 2）就是这条路线做的，题面第一句就是：

> `# WReparse：NTFS 重解析点的安全遍历与确定性审计`
> 平台：Windows + Windows PowerShell 5.1 + NTFS

它在甲方 48 题体系里对应的题材是 **007 win-reparse-002 / 017 windows-junction-boundary-002**，两题均被评"Windows 价值高"。**也就是说：我们不缺做 Windows 机制题的能力，缺的是把这条路线固定成默认路线。**

### 3.2 它的五个缺口（对照 R1–R6）

| 缺口 | 证据 | 对应要求 |
|---|---|---|
| **没有任何 Windows 价值判据** | `validate_requirement_conformance.py` 全 302 行只查：必备路径、TOML/JSON 可解析、ID/版本一致、rubric 权重=1.0、judge.toml 的 `source_sha256`、instruction 六个章节、`run.ps1` 只调一次 prepare、`test.ps1` 有 "generated/do not edit" 标记、私有路径与凭据扫描。**反事实/机制依赖一条都没有。** 5 个 `references/` 也无此内容 | R5 |
| **默认交付口径不含参考解** | `references/harbor-fourpiece.md:20`：「`solution/` may exist locally for Golden validation but is hidden and **must never be submitted**」；`FEISHU_WRITEBACK.md`（217 那次）也确认「已核对包内**不含** `solution/` 与 `source.json`」。只有在收件方显式要求时才切 `references/standard-delivery.md`（该模式**包含** `solution/**`） | R1 |
| **job 归档层无规范** | 全部文件里 `task_checksum` 出现 **0 次**；`verifier.log` 仅在 `package_standard_task.ps1:127` 作为"可选收集文件名"出现。217 的 job 目录是 `jobs/<时间戳>-candidate-<model>-01/{job.json,agent/,verifier/}`，与甲方 `validate_model_jobs.py` 要求的 `jobs/config.json+lock.json+result.json+job.log` + `ctl-*` 语义目录完全不同 | R2 / R3 |
| **INVALID 只停在原则层** | 只有 `SKILL.md:109`「distinguish functional failures (`0`) from infrastructure failures (`INVALID`)」与 `qualification-gates.md:12` 一句原则；没有"如何写 `run_tests.ps1` 才能输出 INVALID""INVALID 时不得留下 reward 文件"这类实现契约 | R6 |
| **模型矩阵规则与甲方现行口径相反** | `qualification-gates.md:27` 要求 `sum(OPUS) > sum(QWEN)` **严格大于**；`SKILL.md:144-149` 仍把 GLM/Kimi 列为必需。而甲方 218 返修原文：「**四模型全部有效 0 分按现行规则允许，不需要因为平分返修**」，且 2026-10-13 起 GLM/Kimi 已不再必需（`references/01-spec-requirements.md:18`） | 反向阻塞 |

### 3.3 实测：generate-win 产物的 job 层在甲方最新校验下 FAIL

用甲方检查器（`harbor-windows/_reference/windows-harbor-qc/scripts/validate_model_jobs.py`）跑 217 的 `jobs/`：

```
pass  : False
errors: 20
  - jobs/ is missing Harbor parent job file: config.json / lock.json / result.json / job.log
  - jobs/ must contain exactly 14 Harbor job directories, got 1
  - jobs/ contains 0 qwen / opus / glm / kimi / oracle / nop jobs
结果已写入 harbor-windows/_qc_runs/windows-mechanism-rework/validate-217-jobs-result.json
```

> 口径说明：217 是 2026-10-07 的产物，甲方 job 层规范其后有更新，**不能据此说 217 当时不合格**（它当时按旧版 `run_qc.py` 通过）。这条实测要说明的是：**沿用 generate-win 的归档形态交付，在今天的甲方校验下必然 FAIL**，R2/R3 必须另做归档协议转换。

### 3.4 根因：generate-win 照的那份"权威需求文档"里**根本没有 Windows 价值条款**

这是本次排查最重要的发现之一。`generate-win/SKILL.md` 让每次任务都先拉取甲方需求文档
（`https://vcnuhsx1gwu0.feishu.cn/wiki/BX1zwQR3kiohuakp3BccxTNdnMc`，《Outside Harbor Windows 题包格式培训 Demo》），
并声明"Treat the fetched document as the authoritative task-package specification"。

**2026-10-14 实时拉取该文档（`requirements-live.txt`，13.7 KB）逐节核对**：全文 7 节讲的是
文件树、每类文件写什么、注释规范、三分钟读包、发布前检查清单，
**没有任何"反事实判定""平台无关则不合格""必须依赖 Windows 专属机制"的要求**。
与 Windows 价值最接近的只有第 6 节一条：

> - [ ] 特殊平台用例（断网、无管理员、Windows 安全语义）在题面或测试矩阵中有明确标识。

也就是说：**generate-win 忠实执行了它拿到的规范，而这份规范不含 Windows 专属价值这一项；
甲方质检却把它当硬判据。** 这正是"skill 与验收口径错位"的根因，也说明：

- 修 skill 的第一步不是抄 generate-win，而是**把甲方质检口径（windows-value.json 的逐题评估 + 专家修复步骤第 3 条）显式并入规范**；
- `solution/**` 的口径两份文档并不冲突：需求文档第 2 节的标准树**包含** `solution/`，只是"**普通模型资产**的发布范围不应包含"。
  R1 要的是**验收侧**参考解 —— 剔除它的是 generate-win 的"默认四件套提交口径"，不是需求文档。

### 3.5 结论

> **不要整包替换成 generate-win。** 正确做法是"**机制取自 generate-win 的选题路线，门禁与验收沿用并强化 harbor-windows 体系**"：
> - 默认选题改成"真实上游 Windows 专属缺陷"（generate-win 第 3 步）；
> - 把 `02-windows-value.md` 的反事实判定做成**可复算的门禁产物 + 校验脚本**（这是两份 skill 都缺的）；
> - 交付默认切到"含 `solution/**` + 隔离证明"的验收侧口径（generate-win 的 `standard-delivery` 已有雏形，可照搬）；
> - job 归档按 218/219 的新协议（`cases[]` + `status`、`verifier/verifier.log`、`ctl-oracle-*`/`ctl-nop-*`、`task_checksum` = 包 dirhash）重建。

---

## 四、同行怎么实现（可直接抄的手法）

### 4.1 分级与最佳样本

43 条被评估题：**高 37 / 中 8 / 低 3**。低的三条是 `004 wfflab__wchunk-216`、`005 wfflab__wfmt-215`、`029 windows-directory-marker-001`。

按"发现数最少 + Windows 价值高"筛出的第一梯队（完整表见同级 `issues_by_task.csv`、`windows-value-tiers.md`）：

| key | task_id | 问题/风险/证据不足 | 甲方评价 |
|---|---|---|---|
| 019 | win-fs-001 | **0 / 2 / 0** | NTFS ACL/ADS/元数据与真实原子替换观察；Windows 价值高 |
| 021 | windows-named-pipe-framing-001 | 0 / 2 / 1 | NamedPipe 消息分帧与总超时；Windows 价值高 |
| 031 | windows-file-attributes-003 | 0 / 2 / 1 | 文件属性 Hidden/System 位保留；Windows 价值高 |
| 002.2 | windows-d6-0007 | 1 / 0 / 2 | NTFS 文件身份、安全描述符、批发布回滚；Windows 价值高 |
| 007/008/010/036 | win-reparse-002 / win-job-005 / win-hardlink-003 / windows-registry-patch-001 | 1 / 1 / 0 | 均为 Windows 价值高 |

### 4.2 三层锁定（C 组归纳，含原始出处）

**① 题面层：把机制名写进"可验收行为"，而不是写在背景里**

- 019 `instruction.md:5`：`目标是真实的 Windows NTFS 语义，不需要实现其他操作系统版本。`
- 019 `instruction.md:33-35`（R2）：读进程授予 `FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE` 时发布必须成功，且旧句柄仍读到完整旧内容；**不能先删除再创建，也不能原地截断/写入**。
- 021 `instruction.md:11`：`验收使用真实 Windows 管道和外部独立服务进程。`
- 036 `instruction.md:7`：值类型必须按 `REG_DWORD` 32 位无符号位模式保存。
- 017 `instruction.md:1`：`所有重解析点都必须跳过，包括指向根目录内部的链接。`

> ⚠️ **这两个句式的区别决定成败**：
> - ✅ **排他声明**（019 L5）：「目标就是真实 Windows NTFS 语义，**不需要实现其他操作系统版本**」——这是把 Linux/macOS 排除出验收范围，**加强** Windows 属性。
> - ❌ **免责声明**（我方 216/218 的 `WINDOWS_VALUE.md`）：「本题**不主张** Windows 反事实价值，按**通用编码能力**归类」——这是**自我否认**，被甲方当作不合格的直接证据引用。
> 两者只差一句话，结论完全相反。

**② 环境层：用真对象做能力探针，探针不成立即 INVALID（不是判模型失败）**

- 021 `validate_environment.ps1:2-3`：`if(-not $IsWindows ...){exit 1}` + 引用 `[IO.Pipes.PipeTransmissionMode]::Message`。
- 036 `validate_environment.ps1:2-5`：PS 版本 + `OSVersion.Build -ne 20348` throw + 真建/删 HKCU 子键。
- 019 `Verifier.cs:601-602`：`PlatformID.Win32NT` + `DriveInfo.DriveFormat == "NTFS"` 双闸门，不满足则全部用例 `validity=INVALID`。
- 021 `task.toml:18-27` 把 `os/edition/build/architecture/locale/shell/filesystem/network_mode` 写成机器可读元数据；`Dockerfile` 只 `FROM ...:7.5-windowsservercore-ltsc2022` + `COPY workspace/`。

> B 组的重要发现：**环境层是同模板复用的**——031 与 024 的 `environment/` 下 7 个文件**逐字节相同**，017 与 037 同样 7 个全同。Windows 绑定强度几乎全部由 **`instruction.md` + `task.toml` + `tests/run_tests.ps1`** 三个文件承担。我们复用这套不需要重造环境层。

**③ 验证层：验证器自己持有内核对象，再观测候选有没有操作同一个对象**

这是最值得抄的一档，也是"无法在非 Windows 上绕开机制只对答案"的根本原因：

| 手法 | 出处 | 为什么跨平台实现必翻车 |
|---|---|---|
| 用 `CreateFileW` 真持有共享句柄，`share` 位决定候选该成功还是该拿共享冲突 | 019 `Verifier.cs:208,223-231,417,451,490` | 共享模式是内核行为，纯逻辑模拟无法产生真冲突 |
| `FindFirstStreamW/FindNextStreamW` 枚举 ADS 并逐流哈希 | 019 `Verifier.cs:203-206,234-252` | 非 NTFS 无数据流概念 |
| `CreateHardLinkW` 造硬链接身份，`GetFileInformationByHandle` 取 VolumeSerialNumber+FileIndex | 019；002.2 `test_fail_to_pass.ps1:50-56,81` | 路径字符串判等当场暴露 |
| 注入 Deny `0x2`（KEY_SET_VALUE）ACE，再用 **`RegNotifyChangeKeyValue`** 在候选"第一次真写"后撤销写权限 | 036 `RegistryAclGuard.cs:14,31-44`、`run_tests.ps1:237` | **候选若没真写注册表，内核通知不触发，`$guard.Applied` 恒 false，该 F2P 用例必失败** |
| `GetValueKind` + `GetValue(..., DoNotExpandEnvironmentNames)` 读原生类型与未展开原文 | 036 `run_tests.ps1:22,27` | 便捷 API 会把 `REG_EXPAND_SZ` 展开、把类型抹平 |
| `NamedPipeServerStream(Message, Asynchronous)` + 211 字节缓冲 + `IsMessageComplete` 判帧 | 021 `server.ps1:6-7` | Message 模式是命名管道独有；"读到能解析 JSON 就停"在 12KB 报文上必错 |
| 让第二个进程持有同名 Event/Mutex，看候选能否操作同一内核对象 | 018、020 | 命名对象是 `Local\`/`Global\` 内核命名空间 |
| 空闲 CPU 增量把"轮询冒充事件通知"一票否决 | 002.1 `:590-615` | 题面禁轮询，判据是运行时可观测而非扫源码 |
| 独立账号 + Job Object + 私有 window station 运行候选，并用 GuardProbe 自证"读不到/写不到 tests" | 019 `test.ps1:37-63,80-82`、`ExecGuard.cs` | 同时给出 R1 要的**隔离的负访问证明** |

**④ 判分基础设施：INVALID 与 FAIL 严格分离、required 三方一致**（正对 R6 / R3）

019 `tests/test.ps1` 是可直接照抄的范式：

- 任何基础设施异常 → 写 `invalid.txt`、**删除 `reward.txt`**、`exit 4`（L106、L117）；
- required 集合三方比对：`required_testcases.json` ↔ `result.required` ↔ `result.testcases`，数量/唯一性/组别/终态任一不符即 throw（L94-100）；
- 二值分：`expectedScore` 由全 PASS 决定，并校验 `$result.score` 与之相等（L101-102）；
- 候选侧 22s/45s 硬期限 + 杀进程树 + 事后无残留进程校验。

**⑤ 反作弊：把"真的用了机制"变成可观测事实**

- 双向对照：候选自述的 JSON 只作参考，真判据是同进程直接读真实对象（036 `Read-Val`/`Snapshot` vs `Check-Report`）。
- 夹具对抗性设计（B 组精华）：锚点文件名同时含中文+空格+方括号（`文件 [1].txt`）；**文件符号链接起一个满足 `.log` 扩展名的名字**（`filelink.log`）专打"按扩展名收集"的实现；junction 指向根目录内部；属性夹具预置 `SetAttributes($p,39)`，断言 `-band 36 -eq 36`。
- 防"先改后回滚"：`Snapshot -ceq $before` 精确 before-image 断言；`FileSystemWatcher(NotifyFilters.Security)` 零变更断言。
- 防"靠睡眠猜状态"：服务端 `stall_ready`/`stall_ack`/`stall_done`/`disconnect`/`missing` 五种故障模式，让固定 sleep 的实现在期望 `timeout` 的用例上暴露。

---

## 五、落地建议

### 5.1 skill 侧：把"Windows 价值"从判断题变成门禁题 ✅ 已实施（2026-10-14）

在 `harbor-windows/skills/harbor-windows/` 上补三件（`generate-win` 也缺，属两边共同短板）：

1. **门禁产物**：每题必须产出 `metadata/windows_mechanism.json`，含
   `{"counterfactual": {"answer": "否", "reason": "..."}, "mechanisms": [{"name":"NTFS 共享模式","where_in_instruction":"instruction.md#R2","where_in_tests":"tests/run_tests.ps1#L417","f2p_case":"deny_delete_sharing"}], "non_windows_must_fail": "validate_environment.ps1#L2"}` —— 每条机制都要能指到题面条款和测试用例。
2. **门禁脚本**：给 `scripts/validate_package.py` 加一档 `check_windows_value()`，硬性要求
   ① above 文件存在且 `counterfactual.answer == "否"`；② 至少 3 条机制且每条都能在 `instruction.md` 与 `tests/` 中定位；③ 至少 1 条 F2P 用例绑定机制；④ 包内**禁止**出现"按通用编码能力归类""不主张 Windows 价值"之类自认表述（正则直接 FAIL）。
3. **交付口径**：默认改为"含 `solution/**` + `tests/` 隐藏测试 + 隔离负访问证据"的验收侧包（照搬 generate-win `standard-delivery.md` 的形状），四件套只在明确要求时导出。

**实施结果（2026-10-14 已完成）**

| 项 | 落地物 |
|---|---|
| 门禁规则 | [`references/12-windows-mechanism-gate.md`](<../../harbor-windows/skills/harbor-windows/references/12-windows-mechanism-gate.md>)：F1–F6 逐条判据、排他声明 vs 免责声明、题面/环境/验证三层可照抄手法、INVALID 与 FAIL 分离、验收侧交付口径、历史包豁免口径、复验标准 |
| 门禁脚本 | [`scripts/check_windows_mechanism.py`](<../../harbor-windows/skills/harbor-windows/scripts/check_windows_mechanism.py>)（可独立运行，退出码 `0/1/2`），已接入 [`validate_package.py`](<../../harbor-windows/skills/harbor-windows/scripts/validate_package.py>) 的 `[Windows机制]` 类别 |
| 门禁产物 | 模板 [`assets/metadata-templates/windows_mechanism.json`](<../../harbor-windows/skills/harbor-windows/assets/metadata-templates/windows_mechanism.json>)；实际字段为 `counterfactual` / `exclusive_declaration.quote` / `mechanisms[]{name,instruction_quote,test_ref,f2p_case}` / `non_windows_must_fail{file,evidence}` —— **比原建议更严**：`instruction_quote` 必须与题面逐字一致，`f2p_case` 必须是 `required_testcases.json` 里 group=F2P 的用例 |
| 流程接入 | `SKILL.md`：底线第 1 条改为可复算门禁；阶段 1 产出改双产物；**阶段 4.5 前置门新增"先跑机制门禁"**（A 级、零成本）；阶段 9 校验项与一票否决清单同步；陷阱表 +3 条 |
| 交付口径 | `SKILL.md` / `references/05-delivery-structure.md` / `references/10-windows-ops-pitfalls.md` / `scripts/README.md` 统一为"验收侧交付包（含 `solution/reference/**` + 隐藏测试副本 + 负访问证据）"，修正原"自动排除 `solution/`"表述 |
| 登记 | `_index/known_issues.md` K33、`_index/CHANGELOG.md` 2026-10-14 条目 |

**自测证据**

- 门禁单测 **12/12 通过**（`harbor-windows/_qc_runs/windows-mechanism-rework/gate_selftest.py`）：同行真实合规题 `win-fs-001` 原样 **PASS**；10 个反例（`answer` 答"是"、机制不足 3 条、`f2p_case` 指向 P2P 用例、`test_ref` 文件不存在、题面 quote 不匹配、排他声明不匹配、平台证据不匹配、题面注入自认句、缺产物无豁免、有豁免未开开关）**全部按预期 FAIL**；豁免开关 1 项 PASS 且 F6 仍生效。
- 四包实测 **4/4 FAIL**，自认句定位到具体文件与行号（`gate-result-current4.json`）。
- 返修原因基线复核：2026-10-14 二次拉取飞书，三条 reason 的 SHA-256 与首次一致（`cee0ac2a…` / `81555264…` / `e0224b5b…`），**分析基线未失效**。

> **现状声明**：本轮**只加门禁与口径，未改动四题任何内容**。按甲方专家修复步骤第 3 条，
> 215/216/218 仍需"注入真实 Windows 语义、发新版后重新作答"，或按实际采购分类移出 Windows 池。
> **219 同属此类**：它在飞书上没有返修原因（记录 149，`返修原因` 为空），但门禁同样判 FAIL
> —— 其题材「PE 镜像校验」与三道题同属平台无关的字节层，甲方一旦抽检会得到同一结论，
> 建议与 215/216/218 一并决策，不要因为"暂时没被点名"而漏掉。

### 5.2 选题侧：优先从这张矩阵里选（按同行覆盖度反查我方空白）
| 机制族 | 同行代表作 | 我方现状 |
|---|---|---|
| NTFS 共享模式 / 原子替换 / 整批回滚 | 019、003、016、041 | **空白** |
| NTFS DACL/ACL 继承与保护位 | 002.3、006、011、019 | 空白 |
| ADS / Junction / 符号链接 / 硬链接身份 | 007、017、024、027、031、032、037 | 曾有 217（reparse），**已撤下** |
| 注册表原生类型 / ACL 注入 / 变更通知 | 002.1、015、025、036、039、043 | 空白 |
| 命名对象（Event/Mutex）与 Job Object | 008、018、020、023、038 | 空白 |
| 命名管道分帧 / 进程与管道 | 021、022、040 | 空白 |
| DPAPI 用户作用域 | 026、030 | 空白 |
| 文件系统通知 / 变更缓冲 | 028、042 | 空白 |

### 5.3 返修三段式（对 215/216/218）

1. **先定性质**：三题核心都是"平台无关字节容器 + CRC + 流式 IO"，按 R5 只有两条路——移出 Windows 池占通用名额，或**注入真实 Windows 语义后发新版并重新作答**（专家明文要求，且"新需求不得追溯扣旧样本"）。
2. **最小注入路线**（B/A 组已给出可搬方案，保留原算法不删，只换载体与验收）：
   - **216（wchunk 分块容器）**：容器落盘改到 NTFS 稀疏文件（`fsutil sparse setflag`）+ 索引放 ADS + 去重用 HardLink + 同一性用 FileID；流式读取的验收绑到 `FILE_SHARE_*` 句柄占用（照搬 019 R2/R4）。
   - **215（wfmt 序列化容器）**：加属性位保留断言（031 的 `-band 36 -eq 36` 直接搬）+ 写入前拒绝 junction/symlink（007/017 手法）+ 尾部校验和改为"共享冲突下仍可读"。
   - **218（分段追加日志）**：段目录扫描必须跳过重解析点（017 用例可整体搬）+ 段轮转后的硬链接隔离（037）+ 原子可见性（019）。
   - **另一条更"Windows 原生"的路线**（C 组 E 节）：216 把权威元数据迁到注册表（值类型 + 值名大小写 + 键 last-write `FILETIME`，跨进程写 + 键删除重建做判据）；215 以 NTFS ADS/文件身份/压缩·稀疏属性/`\\?\` 长路径为保真对象（`GetFileInformationByHandle` + 真实流句柄判定）；218 改为 Windows 线程式管道读取的异常归属 + 超时重入 + 线程/句柄残留（命名 Event 门控 EOF + `threading.excepthook`）。
3. **再补 R1–R4、R6**：参考解与隐藏测试进交付包、冻结后整批重跑并让 `task_checksum` = 包 dirhash、job 归档换 218/219 新协议（`cases[]`+`status`、补 `verifier/verifier.log`、控制组用 `ctl-oracle-*`/`ctl-nop-*`）、`run_tests.ps1` 改成"缺测/执行故障 → `invalid.txt` + 删 `reward.txt` + exit 4"（照抄 019 `test.ps1`）。

### 5.4 同行的共同缺口（我方可以反超的地方）

对标不是单向的。B/C 两组都记录了对方的短板，这些正是"即将满足交付标准"的题的剩余缺口，做新题时避开即可领先：

| 缺口 | 证据 | 出处 |
|---|---|---|
| 声明了 `filesystem="NTFS"` 却**没有运行期卷类型断言** | B 组：本批 5 题都没有 `DriveInfo.DriveFormat` 检查（对比 019/002.2 有） | `notes/B-*.md` §4 |
| 没有机制能力探测，只有版本号检查 | 同理；对比 002.6 真造 ADS 探针、043 注册表 kind roundtrip | 同上 |
| 未写"不需要其他操作系统版本"式排他声明 | 5 题全部没有 | 同上 |
| 基础设施错误前缀未统一，导致 INVALID 可能被误判为候选失败 | 037 的硬链接夹具漏了 `Infrastructure:` 前缀 | 同上 |
| 用例模板残留未清理 | 018/020 的 `run_tests.ps1` 残留了与命名对象无关的 `HKCU\Software\OutsideHarborBench\...` 建删键代码（018:7,10、020:9,12） | `notes/C-*.md` 备注 |

---

## 六、证据索引

| 内容 | 位置 |
|---|---|
| 三条返修原因原文 + R1–R6 归纳 | `harbor-windows/_qc_runs/windows-mechanism-rework/返修原因-三条-20261014.md` |
| 飞书原始应答 | 同上目录 `feishu-raw.json` |
| 甲方需求文档实时全文（用于核对是否含 Windows 价值条款） | 同上目录 `requirements-live.txt` |
| 甲方 job 层校验跑 217 的实测结果 | 同上目录 `validate-217-jobs-result.json`、脚本 `validate_217_jobs.py` |
| 门禁单测（12 项）与四包门禁实测 | `harbor-windows/_qc_runs/windows-mechanism-rework/gate_selftest.py`、`gate-result-current4.json` |
| 返修原因基线复核（二次拉取哈希一致） | 同上目录 `feishu-raw-recheck.json` |
| 门禁规则 / 脚本 / 模板（已实施） | `harbor-windows/skills/harbor-windows/references/12-windows-mechanism-gate.md`、`scripts/check_windows_mechanism.py`、`assets/metadata-templates/windows_mechanism.json` |
| 217 题包参考（generate-win 路线产物） | `harbor-windows/_qc_runs/windows-mechanism-rework/217-package/` |
| 48 题发现数汇总 | 本目录 `issues_by_task.csv`、脚本 `summarize_issues.py` |
| 48 题 Windows 价值分级 | 本目录 `windows-value-tiers.md`、脚本 `classify_windows_value.py` |
| 同行源码选段还原（19 题） | 本目录 `extracted/<key>/`、脚本 `extract_sources.py` |
| 三份机制逆向分析 | 本目录 `notes/A-*.md`、`notes/B-*.md`、`notes/C-*.md` |
| generate-win skill 全文 | `deliverables/2026-10-14_generate-win/` |
