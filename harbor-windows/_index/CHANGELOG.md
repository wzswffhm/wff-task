# CHANGELOG —— harbor-windows 题包目录

## [wfflab__wvas-216 · 替换 wchunk-216 槽位：改用 Windows 虚拟地址空间审计] - 2026-10-14

### 变更原因

甲方 2026-10-14 判定原 216 槽位的 `wfflab__wchunk-216` 为「通用编码能力」——题目与验收全部是平台无关的
长度前缀记录容器 / CRC / 流式 IO 语义，**没有 Windows 专属行为**，不满足 Windows 题要求；
同批另有 `wfflab__wfmt-215`（NTFS 稀疏）、`wfflab__wlogseg-218`（日志轮转共享删除）同期返修。

### 处置

- 新增题包 `wfflab__wvas-216` v1.0.0（新 task_id，替换 216 槽位；`wfflab__wchunk-216` 实物保留为历史）。
- 方向：**进程虚拟地址空间审计**。被测缺陷来自公开上游 `psutil` 提交
  `01bb959957d99e582b0f391534bb7462f29ff17e`（issue #216）：`Process.memory_maps()` 在 Windows 上
  地址被截断为 32 位、保留（`MEM_RESERVE`）区间不可见、`\Device\HarddiskVolume...` 形态路径
  调用方无法直接打开、匿名映射与无文件背衬区分的缺失。
- Windows 机制：判分期真实调用 `VirtualQueryEx` / `GetMappedFileNameW` / `QueryDosDeviceW`，
  并另起目标进程独立测量；Linux 上无对等机制。
- 题面：无答案、无引导性注释、不含任何运行命令；acceptance 侧资产（`solution/`、隐藏套件）与模型隔离。
- 评分：纯程序化二值（`formal_score = 1 当且仅当 run_validity == VALID 且全部 required 用例 PASS`），
  required 16（F2P 8 / P2P 8）。
- 轮次：控制组 golden 3×1 / no-change 3×0 全 VALID；模型轮 Opus×3 = [1,1,1]、Qwen×3 = [1,1,0]，
  区分度准入通过（Opus 3 > Qwen 2）；按甲方口径不跑 GLM/Kimi。
- task checksum：`b925e1c7f68e6954805fa39e6ea584577ced25f87a74d58fb7325b288469461b`（12 个 Harbor job 全部一致）。

## [skill 改造：Windows 专属机制门禁 F1–F6 + 验收侧交付口径] - 2026-10-14

### 变更原因

甲方 2026-10-14 在飞书 wff 表给出三条返修原因（`wfflab__wchunk-216` / `wfflab__wfmt-215` /
`wfflab__wlogseg-218`，记录 90 / 109 / 148），核心判定是：

> 题目和验收是平台无关的容器格式 / CRC / 流式 IO，**没有 Windows 专属行为，不满足 Windows 题要求**。
> 需要按实际采购分类处理，**不能只加 Windows 标签**。

并**直接引用包内自认句作为证据**：

> `verifier/WINDOWS_VALUE.md` 也明确写了「本题不主张 Windows 反事实价值，按通用编码能力归类」。

复查发现根因不在判据缺失（`references/02-windows-value.md` 的反事实判定本来就完整），而在三处失效：

1. **判定不留痕** —— 阶段 1 只要求产出 `labels.json`，没有任何字段要求"机制 → 题面条款 → 测试用例"的锚点；
2. **判定不校验** —— `scripts/validate_package.py` 里**一条 Windows 价值检查都没有**，平台无关的题照样过本地校验；
3. **自认句反成证据** —— 包内 `WINDOWS_VALUE.md` 的自我降格表述被甲方引为不合格证据。

### 变更内容

1. **新增硬门禁 `scripts/check_windows_mechanism.py`（F1–F6，可复算、可单独运行）**：
   读 `delivery-extras/tasks/<task-id>/metadata/windows_mechanism.json`，校验
   ① 门禁产物存在；② `counterfactual.answer = 否` 且有理由；③ 排他声明在 `instruction.md` 逐字出现；
   ④ `mechanisms` ≥3 条，每条 `instruction_quote`（题面逐字）+ `test_ref`（`文件#L起-L止`，行号在范围内）
   + `f2p_case`（必须是 `required_testcases.json` 中的 F2P 用例）；
   ⑤ `non_windows_must_fail` 指向真实文件、证据逐字且含平台判定关键字；
   ⑥ **包内不得出现自我否认 / 通用化 Windows 价值的表述（永不豁免）**。
2. **接入 `scripts/validate_package.py`**：新增 `check_windows_value()`，输出 `[Windows机制]` 类别，
   在平铺、单题、多题目录三种模式均已挂载。实测四包全部 FAIL、同行合规题 `win-fs-001` PASS。
3. **新增 `references/12-windows-mechanism-gate.md`**：门禁规则、**排他声明 vs 免责声明**的关键区分、
   题面/环境/验证三层可照抄手法清单（共建内核对象持有、`CreateFileW` 共享模式、
   `RegNotifyChangeKeyValue` 反短路、`GetFileInformationByHandle` 文件身份、`IsMessageComplete` 分帧、
   `GetValueKind` + `DoNotExpandEnvironmentNames` 原生类型、INVALID 与 FAIL 分离、对抗性夹具设计）、
   验收侧交付口径、历史包豁免口径、复验标准。
4. **交付口径（R1）**：明确三种范围 —— 完整本地题（含 `solution/**`）、普通模型资产（不含）、
   **验收侧交付包（默认提交形态，含 `solution/reference/**` + 隐藏测试副本 + 隔离负访问证明）**；
   修正 `SKILL.md` 与 `scripts/README.md` 中"自动排除 `solution/`"的旧表述；
   `references/05-delivery-structure.md` 新增「三种交付范围必须分清」一节。
5. **新增模板 `assets/metadata-templates/windows_mechanism.json`** 并登记到该目录 README。
6. **`SKILL.md`**：四条底线第 1 条改为可复算门禁；阶段 1 产出改为双产物（`labels.json` +
   `windows_mechanism.json`）；阶段 4.5 前置门新增"先跑机制门禁"（A 级、零成本，不过就别往下走）；
   阶段 9 校验项与一票否决清单同步；常见陷阱新增 3 条（自认句、验收包缺参考解、缺测记 0 分）。
7. **`references/02-windows-value.md`**：新增「判定必须留痕」「排他声明 ≠ 免责声明」
   「判定前先看的三件事」，预筛清单扩到 11 项。

### 复验证据

- 门禁自测 `_qc_runs/windows-mechanism-rework/gate_selftest.py`：**12 项全过**
  （正例 019 原样 PASS；反例 10 项全部按预期 FAIL；豁免开关 1 项 PASS 且 F6 仍生效）。
- 四包实测：`_qc_runs/windows-mechanism-rework/gate-result-current4.json`（4/4 FAIL，
  自认句定位到具体文件与行号）。
- `py_compile` 两个脚本通过；`validate_package.py --package harbor-windows` 正常输出
  `[Windows机制]` 类别。

### 待办 / 声明

- **四题未做任何内容改动**（本轮只加门禁与口径）：按甲方专家修复步骤第 3 条，
  须"注入真实 Windows 语义、发布新版后重新作答"，或按实际采购分类移出 Windows 池。
- **不得只删除自认句** —— 删掉只让门禁变绿，判定依据仍在题面与测试里，
  且会被额外记一条"整改不实"。
- 历史包不追溯改判：可用 `--allow-legacy-exempt` + 包内 `WINDOWS_MECHANISM_EXEMPT.md`
  把 F1–F5 降级为 FLAG（F6 除外），该标记文件**交付前必须删除**。

## [chunk-216 与 wfmt-215 质检返修：1.2.0 → 1.2.1 / 2.1.0 → 2.1.1] - 2026-10-12

### 变更原因

质检合并报告（专家修复详解版）004 / 005 号条目对 `wfflab__wchunk-216`（zq-id=11）与
`wfflab__wfmt-215`（zq-id=12）各提出 6 条问题，两题条目逐字同构：

1. ZQ-01 流式测试引入未声明的 8192 字节读块阈值（QD-SP-02 / VV-02 / VV-03）；
2. ZQ-02 Kimi 0 分混入 API 配额失败（VV-27 / VV-32 / VV-33）；
3. ZQ-03 Windows 专属价值较低（QD-SP-12 / QD-SP-18）；
4. ZQ-04 50% 评审 Rubric 没有逐模型评分证据（VV-14 / VV-19 / VV-30）；
5. ZQ-05 judge.toml 无法按标准 TOML 解析（FC-08 / FC-09）；
6. ZQ-06 模型可读取公开仓库测试，缺手册隔离条款的适配说明（QD-IN-02 / QD-IN-06）。

### 变更内容

1. **流式判据（两题）**：删除 `max_request <= 8192`（215 另有 `bytes_read < len(blob) // 4`）硬阈值；
   改为完整消费 + 「容器读满时仍未产出的记录条数」按 1/8 规模对照（`pending(大) <= max(pending(小) × 2, 8)`）
   + `max_request` 规模对照；新增尾部校验和用例（216 `p2p-stream-tail-checksum-is-rejected`、
   215 `f2p-stream-tail-checksum-is-rejected`）。任何块大小（含 64 KiB 定长缓冲）不再被误杀。
2. **无效槽位**：两包新增 `jobs/invalid-slots.json` 与 `jobs/INVALID-SLOTS.md` 注解层，
   记录 Kimi 的 HTTP 429 `AccountQuotaExceeded` 原文、起止时间、失败前轮次、候选指纹与镜像 digest；
   历史 `jobs/` 记录未改写；替代规则统一，本轮未重跑。
3. **Windows 价值与采购分类**：两包新增 `verifier/WINDOWS_VALUE.md`，逐断言族映射 OS 机制，
   结论为**通用编码能力（Windows 运行时执行）**；`_index/tasks_index.csv` 的 `primary_direction`
   改为「通用编码能力」、`windows_target` 标注为执行平台；Windows 专属化候选列入"未实施"。
4. **评分口径**：`tests/rubric.json` → `programmatic-v3`、`verifier/rubric.conditions.json` → `rubric-conditions-v3`，
   删除 4 个从未产出过分值的 `llm_judge` 项，程序化权重归一化到 1.0（215：0.20/0.20/0.20/0.15/0.25；
   216：0.30/0.12/0.20/0.18/0.10/0.10），`judge.toml` 同步 `programmatic_weight = 1.0` / `llm_judge_weight = 0.0`，
   并写入**版本化废止说明**：配置改动使声明口径与既有生效分一致，不是降低标准。
5. **judge.toml**：修复第 7 行注释续行缺 `#` 导致的 `Invalid statement (at line 7, column 1)`；
   用 Python 标准库 `tomllib` 验证可解析；`source_sha256` 指向修复后的 `rubric.json`。
6. **隔离口径**：两包新增 `verifier/ISOLATION.md`（三层清单 + `isolation-adaptation-v1` 版本化适配口径）
   与只读探针 `verifier/negative_access_probe.ps1`；探针在本机以当前身份运行 `verdict=PASS`，
   `environment/validate_environment.ps1` 退出 0。
7. **版本与身份**：包内 `task.toml` / `environment/adapter.toml` / `environment/agent_visible_paths.json` /
   `tests/rubric.json` / `tests/run_tests.ps1` / `verifier/rubric.conditions.json` /
   `verifier/SEALED_MANIFEST.json` 同步升版（216 → **1.2.1**、215 → **2.1.1**），
   `quality_restoration_version` → `20261012.1`；**交付目录名保持飞书镜像名不动**。
8. **required 计数**：216 18 → **19**（10 F2P / 9 P2P）；215 15 → **16**（9 F2P / 7 P2P）。
9. **交付门禁自检修复（质检报告之外）**：两包 `environment/adapter.toml` 的扁平入口 key 与同名
   `[prepare]` / `[validate]` / `[exec_agent]` / `[test]` / `[restore]` / `[cleanup]` 表冲突，
   标准 TOML 解析报 `Cannot overwrite a value (at line 38, column 9)`
   （`skills/harbor-windows/SKILL.md` §4 已记录「215 v2.1.0 与 216 v1.2.0 带着该缺陷交付甲方」）。
   按「扁平 key 保留、冲突表名改掉」改为 `[entry.*]`，字段值未改；`tomllib` 全文件解析通过。
   该文件不参与判分链路，控制组结论不受影响。
10. **`task.toml` 删除 `docker_image`**（2026-10-13 起的新规范：SKILL.md L198–207、
   `references/06-acceptance-gates.md`「已知差异」节）：基础镜像只由 `environment/Dockerfile`
   的 `FROM` 声明并 pin 到不可变 digest。两包删除该字段，Dockerfile 未改；甲方
   `inspect_delivery.py` 会因此报 `Task has no pinned Docker image`，属**预期差异**、保留不复原；
   本地 `validate_package.py` 则要求该字段不得出现（见 `known_issues.md` K29、K27）。
11. **模型区分度门禁放宽**（2026-10-12）：`_reference/windows-harbor-qc` 原先"Qwen 与 Opus
   同时全满分即 FAIL"的一票否决改为与 skills 侧一致的口径 —— 总分相等时（含双方三轮全满分）
   由 `testcase_pass_sum` 严格分出高下，`qwen_opus_full_score` / `all_models_full_score`
   仅作报告记录。QC 工具包内脚本、测试（12 项单测全过）与 5 份文档已同步（`known_issues.md` K30）。

### 复验证据

- 控制组（本机 Windows，Python 3.13.15 + pytest 9.1.1，判分侧由包内 `verifier/` 提供）：
  - `wfflab__wchunk-216` 1.2.1：Golden 19/19 `formal_score=1`、no-change 9/19 `formal_score=0`；
  - `wfflab__wfmt-215` 2.1.1：Golden 16/16 `formal_score=1`、no-change 7/16 `formal_score=0`；
  - 归档：`_qc_runs/refit-215-216/result-{golden,nochange}-{215,216}.json`、
    `negative-access-{215,216}.json`、`validate-env-{215,216}.txt`。
- 无效槽位：`jobs/invalid-slots.json`（两包）；未重跑，槽位开放。
- 逐条闭环与"未实施事项"：各包根 `REFIT-2026-10-12.md`。

### 待办 / 声明

- Windows 专属化改造**未实施**；如需 Windows 专属评测须立项发新版并**重新作答**，
  新需求不得追溯扣旧样本。
- 历史试次与历史分数**未重评**；`jobs/` 未改写；Kimi 槽位待配额恢复后按同一计划槽位重跑。
- **历史 `jobs/` 的身份已随本次返修失效**：按 `skills/harbor-windows/SKILL.md` 第二条铁律
  「跑分对象必须与最终交付包同一份内容」，正式提交前必须在 215 2.1.1 / 216 1.2.1 上
  **整批重跑**（对照组 + 模型轮次）并刷新 `jobs/`；本轮只完成本机控制组复验
  （Golden 1 / no-change 0）与甲方 `inspect_delivery.py` 静态自检 —— 该脚本因 `task.toml`
  不写 `docker_image` 而报**预期 FAIL**（`Task has no pinned Docker image`），属规范要求，
  不得为过检查写回字段（见 `known_issues.md` K27、K29、K28）。
- **`delivery-extras/` 伴随材料按口径不新增**：`skills/harbor-windows/SKILL.md` L356 要求该目录，
  但本批 4 个交付包原本均未提供，按甲方口径「原本没有就不用加」处理，**不生成骨架**；
  `validate_package.py` 的 `[FAIL] [交付材料] 未提供 delivery-extras/ 目录` 据此保留为已知现状
  （见 `known_issues.md` K31）。
- `_index/checksums.sha256` 覆盖的是**平台发布形态快照**（`wfflab__wfmt-215/…`，含 `extras/`、`jobs/`），
  不覆盖本次返修的 `*-delivery/` 目录；交付包内文件哈希以各包 `verifier/SEALED_MANIFEST.json` 为准。

## [wreparse-217 再次加深：1.2.0 → 1.3.0（D1–D6 激进档）] - 2026-10-09

### 变更原因

1.2.0 按 215 的 L4 设计加深后，四模型 8 场验证**全部满分**（Qwen 3×36/36、Opus 3×36/36、
Kimi 1×36/36、GLM 1×36/36），`run_model_validation.py --score-only` 判定 **False**
（`各模型最终积分相同且不全为 0（Opus 3 vs Qwen 3）`）→ 区分度失败。
根因是加深**只增加了"要检查什么"，没有改变"答案可从文档直接抄出"**这一本质。

### 变更内容（D1–D6）

1. **D1 契约黑盒化**：`docs/REPARSE-CONTRACT.md` 删除 §2/§3/§4/§5/§6/§7 的规则文本，
   改为 **15+ 个实测样例**（8 条 reparse Record 对照、空树完整 JSON、`-MaxDepth` 0/-1/1 三组、
   `-Follow` 的 stats 与 errors、`link-in\readme.txt` 前缀、canonical/within_root 对照、
   `Z/Ä/ö` 实测次序、7 个错误码的实测 Message），并明示"唯一允许照抄的只有 API 签名表"。
2. **D1 题面**：`instruction.md` 的「必须满足的行为」12 条规则复述与「用户可见验收」17 条
   答案式断言全部去答案，改为"只给要覆盖的情形、不给期望值"；新增**验收 18 可复现自证脚本**。
3. **D2 矛盾源**：新增 `docs/REPARSE-CONTRACT.draft.md`（含 9 处与正式契约/实测相反的陷阱，
   如"报告含 GeneratedAt 时间戳"、"`-Follow` 默认开启"、"`LinkType` 非空即重解析点"、
   "直接用 `Sort-Object`"）；`assets/observed-provider-facts.json` 6 → **16 条纯观测**
   （三种文化下的 `Sort-Object` 实测、reparse tag、相对目标解析探测、depth/maxdepth 探测等），
   只给数据不给结论。
4. **D4 夹具**：`tests/prepare.ps1` 新增 8 层深链（`level1..level8` + 两个文件）。
5. **D3 判据**：`tests/run_tests.ps1` +24 条检查 → **60 条**；
   `required_testcases.json` 36 → **60**（45 F2P / 15 P2P）；
   `rubric.json` 9 项权重保持合计 1.0、60/60 全覆盖，`task_version` → 1.3.0。
6. **D5 冒烟测试**：`tests/test_wreparse_basic.ps1` 不再检查 `Records/Errors/Stats` 字段名
   与 JSON 结构，通过它完全无法推断报告形态。
7. **版本与元数据**：`task.toml` / `source.json` / `tests/run_tests.ps1` → **1.3.0**；
   `difficulty` 保持 **L4**、step 上限保持 **40**（与其它题包口径一致）。

### 复验证据

- **本机控制组 3+3**（`_qc_runs/controls_217_v130.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / **60 of 60**；
  NOP 3 次全部 `VALID` / `formal_score=0` / 22 of 60（15 个 P2P 全过 + 7 个 F2P 过）。
- `task_hash` 由 `tree_hash()` 重算（排除 `jobs/` 与 `platform_import.json`）。
- 已砍掉三条不可行判据：`access_denied`（判分进程为管理员会绕过 ACL）、UNC（容器
  bind filter 语义不同）、同名不同大小写决胜（NTFS 不允许同名文件）。

### 待办

- 三模型区分度必须重跑；若仍全满分，需进一步加深（候选方向：删除契约文档、只留 assets）。
- 甲方 QC 动态门禁需 Windows 容器，待环境恢复后重跑。


## [wreparse-217 难度加深 L3 → L4] - 2026-10-09

### 变更原因

`wfflab__wreparse-217` 与 `wfflab__wfmt-215` 同为交付题包，但难度不对等：215 是 **L4**，
217 只有 **L3**。根因在**行为依据的完备程度**——215 的 `docs/FORMAT.md` 是早期草稿、
与真实布局脱节，`assets/` 下的样本才是唯一权威，模型必须逆向；而 217 的
`docs/REPARSE-CONTRACT.md` 把规则逐条写全，模型照抄即可。

甲方 QC 门禁两题都已通过（215：15 项；217：30 项），所以差距不在 QC 是否达标，
而在难度等级本身。

### 变更内容（215 → 217 的 L4 设计复刻）

1. **权威依据分流**：新增 `environment/workspace/assets/observed-provider-facts.json`
   （真机 Windows 11 + NTFS + Windows PowerShell 5.1 实测的 6 条 provider 事实）；
   契约文档新增 §10，声明它只规定**语义**、不规定 provider 层返回值形状，
   两者在实现细节上冲突时以实测事实为准。
2. **自我一致性陷阱**：新增可见冒烟测试 `environment/workspace/tests/test_wreparse_basic.ps1`，
   只验证「模块能导入、报告结构存在、能序列化」。**当前带 23 处契约偏差的实现同样全部通过**，
   与 215「pack 能读回自己的输出、所以可见冒烟测试掩盖问题」同构。
   `instruction.md` 明确声明通过它不代表符合契约。
3. **新增 6 条契约一致性检查**（required 30 → **36**：23 F2P + 13 P2P）：
   模块导出面恰好六个函数（§2）、报告字段集合恰为五项（§3）、排序与宿主 culture 无关
   （§6.1/§6.2）、未给 `-Follow` 时不得报 `cycle`/`broken_target`（§7）、
   普通条目 `InScope` 恒为 `false`（§3.1）、`Target` 类型稳定（§3.1）。
   另把 `target-is-serialised-as-string` 登记为 P2P（合法解修复前后都必须通过）。
4. **夹具增强**：`scanroot` 下新增 `Z.txt` / `Ä.txt` / `ö.txt`。三者的**序数顺序**与
   **区域设置敏感顺序**相反（实测：`Sort-Object` 在 zh-CN 下给出 `Ä, ö, …, Z`，
   序数规则要求 `Z, Ä, ö`），因此把排序委托给 `Sort-Object` 的实现必然失败。
   文件名以字符码构造，避免脚本编码影响。
5. **候选实现新增 5 处可观测偏差**并同步 Golden：导出面放宽为 `*`（psm1 + manifest 两处）、
   用 `Sort-Object` 排序记录、错误列表只按 `Code` 排序、默认扫描也解析目标并报
   `broken_target`、普通条目写入 `InScope`。
6. **版本与元数据**：`task.toml` `difficulty` L3 → **L4**、`[task].version` → **1.2.0**；
   `rubric.json` 新增 `public-surface` 项并把 9 项权重重新配平到合计 1.0；
   `instruction.md` 增补第 9~12 条行为要求与第 12~17 条验收项。

### 复验证据

- **本机控制组**（`_qc_runs/controls_217_v120.json`）：
  Oracle 3 次全部 `VALID` / `formal_score=1` / 36 of 36；
  NOP 3 次全部 `VALID` / `formal_score=0` / 13 of 36（13 个 P2P 全过、23 个 F2P 全挂）。
- **包哈希**：`task_hash = 90354fb76e46943681d514c8f3358a4439d00ec9c1dc8f21d50167bb379eecda`。

### 待办

- 三模型区分度（Qwen ×3 / Opus ×3 / GLM ≥1 / Kimi ≥1）必须重跑，原 `qualified: true`
  （`task_versions: ["1.0.0"]`）不再适用。
- 甲方 QC 工具的动态门禁需要 **Windows 容器**（本机 Docker 当前为 WSL2/Linux 引擎、
  `Containers` 可选功能为 `Disabled`），待环境恢复后重跑。

## [范围对齐 + 标准 Harbor 兼容] - 2026-10-08

### 变更原因

1. **目录材料与实物不符**：`README.md` 与 `_index/` 按完整仓库的 9 / 16 题范围编写，
   而本目录实物只有 2 个题包（`wfflab__wfmt-215`、`wfflab__wreparse-217`），
   且原 9 题清单中**没有**这两题。
2. **题包不满足标准 Harbor CLI 契约**：缺 `[task].name`、缺 `[environment].os/workdir`、
   缺 Windows `.bat` 入口，导致 `Task.is_valid_dir()` 为假，`harbor run --path <题包>` 报 `0 tasks`。

### 变更内容（题包侧）

两题统一：

- `task.toml`：`[task]` 增加 `name = "wfflab/<name>"`；`[environment]` 增加 `os = "windows"`、
  `workdir = "C:\\testbed"`；**不设** `[environment].docker_image`，由 Harbor 构建
  `environment/Dockerfile`。顶层 `docker_image`、`[metadata]`、`[agent]`、`[verifier]`、
  `[task] id/setup/test/golden`、`[policy]` 原样保留，本地 runner 不受影响。
- 新增 `solution/solve.bat`、`tests/test.bat`：Windows 容器只发现 `.bat` 入口，二者仅委托对应 `.ps1`。
- `solution/solve.ps1` 增加**可选**参数 `-WorkspaceRoot`：不传时行为与整改前完全一致。

215 专属：无（Dockerfile 已有 `COPY workspace/ → C:/testbed/`）。

217 专属：

- `environment/Dockerfile` 追加 `COPY ["workspace/", "C:/testbed/"]`（原仅 `FROM`/`WORKDIR`/`CMD`，依赖本地 runner 挂载）。
- 新增 `tests/prepare.ps1`（夹具构建器实现迁入）；`environment/prepare.ps1` 改为**转发**到该文件，
  以承接标准 Harbor 缺失的 prepare 阶段，同时保持本地 runner 的调用路径不变。

### 变更内容（目录材料侧）

- `README.md`：题包清单由 9 题改为实际 2 题；新增「范围声明」与「标准 Harbor 兼容」章节；
  重写单题结构树、校验说明与 `task_hash` 规则。
- `_index/tasks_index.csv`：2 题；`task_hash` 改用可复现的**题包定义树哈希**（规则见 README「校验」）。
- `_index/model_summary.csv`、`model_validation_summary.json`、`model_validation_report.md`：
  按 2 题重建；数值取自各题 `jobs/_index/qualification_summary.json` 与
  `jobs/<run_id>/verifier/checks.json`（逐条 `PASS` 计数）。
- `_index/validation_report.md`、`knowledge_tree_coverage_report.csv`：按 2 题重写（覆盖 12 方向中的 2 个）。
- `_index/EXTERNAL_IMAGES.json`：由 10 个题包改为 2 题；记录本机 Image ID 与基础镜像 ID。
- `_index/known_issues.md`：新增范围声明与 K1–K20 逐条适用性对照；题号对照改为本目录 2 题。
- `_index/checksums.sha256`：按 2 题范围重算（515 个文件，含 `jobs/`）。

### 未重算（需注意）

- `_index/validate-report.json` 仍是**旧 9 题范围**的产物（生成它的
  `skills/harbor-windows/scripts/validate_package.py` 未随本目录交付），其中 `PASS=256` 等计数
  对应旧范围；正式验收前须在当前 2 题范围重新生成。

### 已验证（真实 Windows 容器）

- `Task.is_valid_dir()` 两题均为 `True`；`harbor run --path <题包目录>` **单题直跑**成功。
- 镜像由 Harbor 从 `environment/Dockerfile` 构建；215 另经 `docker build --no-cache` 全新构建（11 步）通过。
- 默认环境（**零扩展**）`--agent oracle` → `Reward 1`。
- 控制与门禁：Oracle ×3 = `VALID/1`、NOP ×3 = `VALID/0`（两题），共 12 条 Harbor 运行记录写入 `jobs/`。
- `jobs/` 历史记录的真实原始件（`agent.log` / `checks.json` / `test.log` / `stderr.log`）已回填，
  并以 `test_log_sha256` 逐条对账：215 = 16/16、217 = 17/17 全部匹配。

### 已知遗留（工具侧，非题包侧）

甲方质检包 `windows-harbor-qc` 的静态引用扫描会把脚本/注释中的路径字面量判为「引用缺失文件」
（连注释都算），且静态失败会硬短路动态门禁；其 `markdown_report` 另存在
`task['static']` 键路径不匹配导致的 `KeyError`。详见
`deliverables/2026-10-08_harbor-windows-整改/README.md` 第八节与最小复现脚本。

## [wfflab__wsync-142 → wfflab__wproc-209 替换] - 2026-10-01

### 变更原因（区分度方向不成立）

`wfflab__wsync-142` v2.1 在四个模型上的最终 VALID 结果：

| 模型 | `model_score_sum` | `testcase_pass_sum` |
|---|---|---|
| Opus 5 | 0.0（19/20/22，共 24） | 61 |
| Qwen3.8-Max-0902 | 1.0（24/23/23，共 24） | 70 |

- 准入条件 ① `Opus > Qwen`：`0.0 > 1.0` → **不成立**（方向相反）
- 准入条件 ② 双 0 时比 testcase：Qwen 非 0，前提不成立；即便按 testcase 比，`61 < 70` 亦**不成立**

继续加大难度无法翻转符号（Qwen 在全部已测维度均 ≥ Opus），故按规范 8.2 走**替换**。

### 变更内容

- 新增替换题 `wfflab__wproc-209`：主方向**进程与执行上下文**（12 方向中第 6 个，原 9 题未覆盖）；
  难度 **L5**；语言 Python；任务类型 bugfix；required **F2P 6 + P2P 7 = 13 条**；
  `task_version` 1.0；`task_hash` `d6f13ab8…`；`image_ref` `wfflab/wproc-windows-bench:wfflab__wproc-209-v1.0`。
- 被测包 `wproc` 2.1.0 的三处缺陷：`Popen.kill()` 只杀直接子进程；`communicate(timeout)` 被后代持有的管道拖成假超时；超时分支丢弃截止前输出。
- `wfflab__wsync-142` **保留在仓库中作为过程证据**，`tasks_index.csv` 标记 `replaced`，不参与本轮交付；
  其 `EXTERNAL_IMAGES.json` 条目 `role` 改为 `replaced_archived`。
- 平台端点无需改动：`wproc-209` 与其余题共用同一套多模型端点。

### 已验证（本机 L2，真实 Windows）

- no-change：`VALID` / `score=0.0` / pytest **6 failed + 7 passed**（89.5 s）—— F2P 全失败、P2P 全通过，正是设计意图。
- Golden：`VALID` / `score=1.0` / pytest **13 passed**（69.9 s）。
- 可见测试 `tests/test_wproc_basic.py` 在 base 与 golden 下均 **10 passed**。
- 平台语义先实测后出题：`scripts/win_probe_proc.py` 6 条假设、5 命中 + 1 刻意对照（`read` 阻塞丢数据 vs `read1` 读多少算多少）。
- `validate_package.py`：**PASS=284 / FAIL=0 / FLAG=5**（FLAG 全部为本题 `extras/evidence/` 五个子目录待生成）。

### 已知未完成

- 镜像仍未构建（`image_digest` 待回填，见 `known_issues.md` K1）。
- `wproc-209` 的对照证据矩阵与多模型区分度待出（见 `known_issues.md` K2/K3/K14）。
- 细节见 `wfflab__wproc-209/extras/remediation_and_retest.md` 与 `quality_review.md`。

## [wfflab__wsync-142 2.0 → 2.1] - 2026-10-01

### 变更原因（区分度不达标）

v1.0 的多模型实测显示 16 条 required 对主流模型过于宽松：Opus 5 三次全部 1.0
（`model_score_sum = 3.0`），Qwen3.8-Max-0902 与 Kimi K3 也均为 1.0。
按规范 8.2，「Opus > Qwen」与「双 0 且 testcase 严格区分」两个准入条件均不成立，
该题区分度不满足准入要求，须整改或替换。经确认采取**整改**路线。

### 变更内容

- `task_version` 1.0 → 2.0；`task_hash` `a06c9ab7…` → `ec4941c1…`；
  `image_ref` → `wfflab/wsync-windows-bench:wfflab__wsync-142-v2.0`。
- required 由 16 条（F2P 7 + P2P 9）扩到 **24 条（F2P 15 + P2P 9）**，新增 8 条 F2P：
  - 只读空目录清理
  - 文件↔目录类型冲突（含仅大小写不同、祖先分量被文件占住）
  - 冲突清理不得误伤无关条目
  - 同尺寸同 mtime 但内容不同必须更新
  - 幂等 + 源 mtime 保真
  - 只读且被占用时必须与「可修复的只读」精确区分
- `instruction.md` 重写，新增症状与验收标准均**完整声明**；未引入题面未声明要求或冷门陷阱。
- `solution/oracle.patch` 重写（`fsops` 增加内容比对/时间戳对齐/类型冲突清障，`planner` 改为内容级变化判定，`mirror` 增加冲突消解与 KEEP 时间戳巡检）。
- `environment/workspace/` 与 `environment/Dockerfile` **未改动**。
- 难度标注 L4 → **L5**（L1–L5 为出题方自定分级，**归纳编号**，规范原文未定义）。
- 细节与实测依据见 `wfflab__wsync-142/extras/remediation_and_retest.md` 迭代 3。

### 追加修正（由真实模型运行反查，同日）→ 升级为 **2.1**

- 两条大小写用例原先写死终态的**名字大小写**（要求保留目标侧原名），超出题面声明
  「文件存在、内容正确、条目不多不少」。已改为大小写不敏感的等价断言；
  `test_patch.diff` hunk 行数 `+1,428` → `+1,440`。
- 影响：Opus 5 `run-1` 由 18/24 → **19/24**（仍不通过 F2P）；`negative_03` 由 18/24 → 20/24。
  其余对照（no_change 0 / golden 1 / negative 0 / equivalent 1）不受影响。
- 按 `task.toml` 自定约定「影响 Tests 的修改必须升级 version」，`task_version` **2.0 → 2.1**，
  身份三元组随之更新为 `478e5057…`，`image_ref` → `…-v2.1`，四处身份文件与
  `_index/checksums.sha256` 已重新落盘。题面与 oracle **未改动**。
- 细节见 `remediation_and_retest.md` 迭代 5；经验已记入 `_index/known_issues.md` K11。

### 已验证

- no-change 独立 3 次均为 0（P2P 全过、15 条 F2P 全失败）；Golden 独立 3 次均为 1；
  干净重建复验一致；3 类反例均 0 分；等价实现（结构不同的写法）得 1 分。
- **v1 解法在新 required 集上失败 7 条**，作为反例 `negative_01_readonly_only` 固化。
- 真实模型：Kimi K3 `run-1` 得 **1.0（24/24）**，证明题目可解；
  Opus 5 `run-1` 得 **0.0（19/24）**，失败集中在类型冲突的删除时序与 mtime 保真。

### 已知未完成

- 镜像仍未构建（`image_digest` 待回填）。
- 多模型区分度复验进行中，结果见 `_index/model_validation_report.md`。

## [目录结构] - 2026-10-01

### 变更
- 取消批次层（原 `delivery-wffw-0001-v1.0` / `delivery-wffw-0002-v1.0`），
  9 个题包平铺为**自包含**目录，彼此独立、互不影响。
- 每题结构：五件套（`task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/`）
  + `platform_import.json`（平台导入 JSON）+ `extras/`（题级伴随材料）。
- 跨题汇总材料移至 `_index/`。
- **身份不变**：9 题的 `task_id + task_version + task_hash` 与调整前完全一致。

## [1.0] - 2026-10-01

### 新增（9 题）
- `wfflab__wpathext-204`：构建工具按名字找不到非 .exe 的可执行文件。主方向：Shell 与自动化；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wps-207`：PowerShell 步骤失败仍然被判定为成功。主方向：Shell 与自动化；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wacl-203`：共享目录发布未让只读权限覆盖整棵子树。主方向：安全与身份；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wsync-142`：属性 / 命名 / 共享语义。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 9 条。
- `wfflab__wreserved-201`：上传服务把 Windows 保留设备名当成普通文件名。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 8 条。
- `wfflab__wads-202`：下载文件归档时丢掉 NTFS 备用数据流。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wrotate-208`：目标序号已有残留时日志轮转失败。主方向：文件系统与路径；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- `wfflab__wreg-205`：读不到 32 位程序写下的注册表配置。主方向：系统管理；难度：L4；语言：Python；任务类型：bugfix；required F2P 6 条、P2P 6 条。
- `wfflab__wencoding-206`：按平台默认编码写文本导致非 ASCII 内容损坏。主方向：编码与区域；难度：L4；语言：Python；任务类型：bugfix；required F2P 7 条、P2P 6 条。
- 标准 Harbor 五件套（schema 1.3）。
- 题级六项伴随材料（metadata / evidence / model_runs / testcase_mapping / quality_review / remediation_and_retest）。

### 已验证
- `wfflab__wsync-142`：no-change 独立 3 次均为 0；Golden 独立 3 次均为 1；干净重建复验一致；
  4 类错误反例均 0 分；等价实现得 1 分。
- 其余 8 题：完成静态结构校验（五件套 / 题面不泄漏 / 身份三元组一致），未执行运行时验证。

### 已知未完成
- 镜像未构建（`image_digest` 待回填）。
- 8 题对照验证未执行；9 题多模型区分度验证未执行。

## 2026-10-02 替换链第三棒：新增 wfflab__wstamp-211（NTFS 时间戳语义）

- `wfflab__wstamp-211`：备份工具库 wstamp 的「同步状态 = 内容 + mtime」缺陷族 +
  Win32 属性事务。主方向：文件系统与路径；难度：L4；语言：Python；bugfix；
  required F2P 8 条、P2P 8 条；task_hash 9a381fd5cce5…。
- 选题依据：多模型运行数据中 Qwen3.8-Max-0902 的唯一失手模式
  （wsync-142 上 test_sync_is_idempotent_and_preserves_source_mtime 3 轮挂 2 次，
  同步只比较内容、漏 mtime 回写分支）；其余考点位于 Opus 已验证可靠区。
- 本机验证：base 8F2P 全失败 / 8P2P 全通过；oracle 全过；
  L2 nochg 0.0 / golden 1.0；对照证据 12 项全符合预期（3 反例 0.0、等价 1.0）。
- 替换链状态：wsync-142（replaced）→ wproc-209（判死）→ winstall-210（判死）→ wstamp-211（验证中）。

## 2026-10-13 甲方规则变更：GLM/KIMI 不再必需（模型 job 14 -> 12）

- **新规则**：GLM-5.3 与 Kimi K3 不再是交付必需项。新生产题包只跑 控制组（no-change x3 / Golden x3）
  + Qwen3.8-Max-0902 x3 + Opus 5 x3，合计 **12 轮 / 12 个 job**。
- **旧包不回退**：216 在规则变更前已按 14 轮跑完并上传，其 jobs 归档保持当时口径，不重跑、不改写。
- **同步范围**：
  - 生产 skill skills/harbor-windows/：SKILL.md、references/01、05、06、07、08、09、10、scripts/README.md（20 处）
  - 质检 skill _reference/windows-harbor-qc/：SKILL.md、references/checklist.md、rule-matrix.md（10 处）
  - 门禁脚本 alidate_model_gate.py（REQUIRED_COUNTS 拆为必需 + OPTIONAL_COUNTS）、
    alidate_model_jobs.py（job 数 12 或 14 均合规）；12 项门禁单测全部通过
- **验证**：仅提交 6 次必需模型运行时门禁 pass=True；GLM/Kimi 出现时仍须恰好 1 次。
- **口径**：本次说明不代表修改或重评了原始产物。

## 2026-10-13 最新质检要求（20261012 批次）写入 skill

- 新增 skills/harbor-windows/references/11-latest-qc-requirements.md（完整版），
  并在 SKILL.md 参考索引接入。
- 新增 _reference/windows-harbor-qc/references/latest-qc-requirements.md（质检侧判据摘要），
  并在质检 SKILL.md 接入。
- 沉淀的 6 条通用要求：
  1. 性能/流式断言不得固定魔法阈值（须用随输入规模增长的规模对比，并完整消费迭代器、独立断言尾部错误）
  2. API 配额/限流/传输失败必须单列无效槽位，不得计入能力分，且不得改写归档树
  3. Windows 价值必须真实映射；否则归入通用编码能力并调整采购分类（禁止只改题名/强加标签）
  4. 声明了评审权重就必须有逐候选证据与合成公式，否则按正式口径版本化废止
  5. judge.toml / adapter.toml 必须能被标准解析器（tomllib）完整读取
  6. 公开测试与隐藏验收必须分层，并以运行时挂载与负访问探针证明隐藏材料不可达
- 来源：甲方质检报告《Windows-48题质检-专家修复详解版-20261012》第 004/005 篇（zq-id=11 / zq-id=12）。
- _reference/windows-harbor-qc/MANIFEST.sha256 重算为 34 条（新增 1 项、内容变更 1 项）。
- 口径：本次说明不代表修改或重评了原始产物；新要求不得追溯扣旧样本。
