# 12 · Windows 专属机制门禁与验收侧交付口径

> 来源：甲方《Windows-48题质检-专家修复详解版-20261012》004 / 005 两节（`wfflab__wchunk-216` 判「Windows 专属价值低」）、
> 甲方 2026-10-14 飞书三条返修原因（216 / 215 / 218）、以及该批次 43 题的逐题价值评估（`windows-value.json`）。
>
> **适用**：所有 Windows 专项题包的**新生产**；返修包按「新需求不得追溯扣旧样本」单独处置（见 §6）。

---

## 0. 为什么要有这道门

甲方判定的原话是：

> 题目主要检查二进制布局、CRC 和流式读取；`task.toml` 及 `verifier/WINDOWS_VALUE.md`
> 明确把它归成通用编码题，测试没有 Windows 专属行为，不满足当前 Windows 题要求。
> 需要按实际采购分类处理，**不能只加 Windows 标签**。

专家给的三条修复步骤（ZQ004-03 / ZQ005-03）：

1. 把题目要求映射到**真正依赖的操作系统机制**；
2. 若保留通用题，明确归入通用编码能力并调整采购分类；
3. **若需要 Windows 专属评测，新增有实际产品需求的 Windows 语义，发布新版后重新作答。**

三道题翻车的真实原因**不是规则缺失**——`references/02-windows-value.md` 的反事实判据本来就写得完整——
而是：

| 失效环节 | 具体表现 |
|---|---|
| 判定不留痕 | 第 1 步只要求产出 `labels.json`，没有任何字段要求"逐条机制 → 题面条款 → 测试用例" |
| 判定不校验 | `scripts/validate_package.py` 里**一条 Windows 价值检查都没有**，题包带着"平台无关"照样过本地校验 |
| **自认句反成证据** | 216/215/218 包内 `verifier/WINDOWS_VALUE.md` 写「**不主张** Windows 反事实价值，按**通用编码能力**归类」——甲方直接引用这句作为不合格证据 |

因此本门禁的三条设计原则：**可复算**（每条证据都能定位到文件与行号）、
**双向锁定**（题面条款与 F2P 用例必须互指）、**禁止自认**（自认句一律 FAIL 且不可豁免）。

---

## 1. 硬门禁 F1–F6

门禁产物：`delivery-extras/tasks/<task-id>/metadata/windows_mechanism.json`
（或题包内 `metadata/windows_mechanism.json`）。模板见 `assets/metadata-templates/windows_mechanism.json`。

| # | 判据 | 判定 |
|---|---|---|
| **F1** | 门禁产物存在且 `task_id` 与包内身份一致 | 缺失 → FAIL |
| **F2** | `counterfactual.answer` = 「否」，且有非空 `reason` | 答「是」或缺理由 → FAIL |
| **F3** | `exclusive_declaration.quote` 在 `instruction.md` 中**逐字出现**（≥8 字符） | 不出现 → FAIL |
| **F4** | `mechanisms` ≥ 3 条；每条 `instruction_quote` 在题面逐字出现；`test_ref` 指向的文件存在且行号在范围内；`f2p_case` 在 `tests/required_testcases.json` 中且 `group == "F2P"` | 任一不满足 → FAIL |
| **F5** | `non_windows_must_fail` 指向包内真实文件，`evidence` 逐字出现且含平台判定关键字 | 不满足 → FAIL |
| **F6** | 包内**不得出现自我否认 / 通用化 Windows 价值的表述** | 命中 → **FAIL，永不豁免** |

`mechanisms` 只有 3 条时给 FLAG（建议覆盖更多机制族），不阻塞。

### 1.1 运行方式

```bash
# 单题
python scripts/check_windows_mechanism.py --task-dir <题包目录>
# 平铺多题 + 落 JSON
python scripts/check_windows_mechanism.py --package harbor-windows --json _qc_runs/<run>/gate.json
# 门禁产物在 delivery-extras 下时显式指定
python scripts/check_windows_mechanism.py --task-dir <题包目录> --extras <delivery-extras 目录>
```

退出码：`0` 通过、`1` 存在 FAIL、`2` 参数错误。
同时已接入 `scripts/validate_package.py`（阶段 9 身份与材料校验），作为 `[Windows机制]` 类别参与 PASS/FAIL 汇总。

### 1.2 F6 命中的表述长什么样

```text
❌ 本题不主张 Windows 反事实价值。          → 『不主张 … Windows』
❌ 按通用编码能力归类 / 入通用编码题池。      → 『通用编码能力 / 题池』
❌ windows_target 标注为执行平台，不作为…    → windows_target 自我降格
❌ This is a platform-agnostic task.         → platform-agnostic
❌ This cross-platform problem does not depend on Windows. → cross-platform + not depend on Windows
```

> ⚠️ **历史包有这类文档时，处置方式是"改题"或"移出 Windows 池"，不是"删掉那段话"。**
> 删掉只让门禁变绿，判定依据仍在题面与测试里；甲方下一轮照样判不合格，
> 而且会额外记一条"整改不实"。

---

## 2. 关键区分：排他声明 ≠ 免责声明

这两句话形态接近、结论相反，是本批次最容易踩的坑：

| | 例句 | 性质 | 效果 |
|---|---|---|---|
| ✅ **排他声明** | 019 `instruction.md:5`：`目标是真实的 Windows NTFS 语义，不需要实现其他操作系统版本。` | 把 Linux/macOS **排除出验收范围** | **加强** Windows 属性；F3 要求登记 |
| ❌ **免责声明** | 216/218 `verifier/WINDOWS_VALUE.md`：`本题不主张 Windows 反事实价值，按通用编码能力归类` | 自我否认被测能力 | 被甲方**直接引为不合格证据**；F6 命中 |

排他声明的推荐句式（任选一种，写进 `instruction.md` 正文，不要只写在元数据里）：

- `目标是真实的 Windows <机制名> 语义，不需要实现其他操作系统版本。`
- `验收使用真实 Windows <对象> 和外部独立<进程/服务>。`
- 环境档位写法（也满足，但需在题面出现）：`环境是 Windows Server 2022 x64 build 20348、PowerShell 7.5.10、NTFS，离线运行。`

> 注意：`Windows PowerShell 5.1 不支持长路径，超 260 字符不在本要求范围内`
> 这类是**可判定性边界说明**，不是免责声明 —— 但它不能替代排他声明。

---

## 3. 题面层：把机制名写进"可验收行为"

**不要**写"可以使用 Windows API"这类许可式表述 —— 那样跨平台写法也能过，正是本次返修的形态。
必须像下面这样，把机制写进**行为要求**：

| 机制族 | 可照抄的题面句式 | 出处 |
|---|---|---|
| NTFS 共享模式 / 原子可见性 | 「若旧目标已被读取进程打开，且它授予 `FILE_SHARE_READ \| FILE_SHARE_WRITE \| FILE_SHARE_DELETE`，发布应成功……**不能先删除目标再创建，也不能原地截断/写入目标**」 | 019 R2 |
| NTFS 元数据 / ADS | 「成功发布必须保留原目标的**创建时间、DACL（包括继承保护状态）、所有已有命名数据流的名称和原始字节**」 | 019 R3 |
| 硬链接身份 | 「任何两个目标若解析为同一个文件（包括大小写/`.`/`..` 路径别名或 **NTFS 硬链接**），必须拒绝……**硬链接身份验证必须利用真实文件系统**」 | 019 R5 |
| 重解析点边界 | 「所有重解析点都必须跳过，**包括指向根目录内部的链接**」 | 017 |
| 文件属性位 | 「必须保留该文件已有的 Archive、System 以及其他属性」 | 031 |
| 注册表原生类型 | 「`FileCount` 为 DWORD，其余为 REG_SZ；恰好这四个值」「`REG_EXPAND_SZ` 必须保存**未展开原文**」 | 002.2 / 043 |
| 注册表变更通知 | 「把定时轮询改造成**注册表原生变更通知**；不得保留任何形式的周期性轮询」 | 002.1 |
| 命名管道分帧 | 「服务端使用 **Message transmission mode**；一条报文可能超过一次读取的缓冲区」 | 021 |
| 共享冲突错误码 | 「`win32` 必须是 Windows 返回的**原始错误码**：32→`SharingViolation`、33→`LockViolation`」 | 003 |
| 跨进程命名对象 | 「用命名 Event/Mutex 做跨进程互认；abandoned 状态须恢复」 | 018 / 020 |

同时要写**负面约束**与**噪声边界**：

- 「拒绝时不能创建或改动目标中的任何文件」（007）
- 「只比较目标原有的 DACL 及其继承保护状态；不要求复制 owner/group」（019 L62）
- 「不得靠固定等待时间推断服务已健康或消息已结束」（021）

---

## 4. 环境层：用真对象做能力探针

要点：**"非 Windows 必然失败"必须放在 preflight，且让全量用例记为 INVALID（而不是判模型 0 分）。**

| 做法 | 范例 |
|---|---|
| OS/build/shell/filesystem 精确匹配，偏离即 throw | 036 `validate_environment.ps1 L2-L3`（PS 7.4.18 + `Build -ne 20348`）；003 `Build -ne 20348`；018/043 要求 PS 精确 =7.5.10 |
| **当场创建真实机制对象**做探针 | 002.6 真造 `Zone.Identifier` ADS，读不到即 `NTFS alternate data streams are unavailable.`；036 真建/删 HKCU 子键；043 注册表 kind/raw roundtrip |
| 平台 + 文件系统双闸门 | 019 `Verifier.cs L601-602`：`PlatformID.Win32NT` + `DriveInfo.DriveFormat == "NTFS"` |
| 卷类型 / 权限令牌硬门槛 | 002.2：64 位 OS + Framework csc + `DriveFormat -eq 'NTFS'` + 管理员令牌 + 夹具文件数 |
| 镜像钉 `@sha256`，禁止浮动 tag | 019 / 021 / 036 Dockerfile；036 另有 `frozen_docker_image_id` |
| `network_mode = "no-network"` | 019 `task.toml L32`、036 `L22` |

> 环境层可以**整包复用**：同行 031 与 024 的 `environment/` 7 个文件逐字节相同，017 与 037 同样。
> 绑定强度实际由 `instruction.md` + `task.toml` + `tests/run_tests.ps1` 三个文件承担。

---

## 5. 验证层：评测器自己持有内核对象

这是"无法在非 Windows 上绕开机制只对答案"的根本。可直接搬的清单：

| 手法 | 范例 | 为什么跨平台实现必翻车 |
|---|---|---|
| `CreateFileW` 真持共享句柄，由 `share` 位决定期望结果 | 019 `Verifier.cs L417/L451/L490`；003 `verify_task.py L170-182` | 共享模式是内核行为，逻辑模拟产生不了真冲突 |
| `FindFirstStreamW/FindNextStreamW` 枚举 ADS 并逐流哈希 | 019 `Verifier.cs L203-252` | 非 NTFS 无数据流概念 |
| `CreateHardLinkW` + `GetFileInformationByHandle`（卷序列号:FileIndex:NumberOfLinks） | 019；002.2 `test_fail_to_pass.ps1 L49/L81`；002.6 `run_tests.ps1 L117-196` | 路径字符串判等当场暴露 |
| 注入 Deny `0x2` ACE，再用 `RegNotifyChangeKeyValue` 在候选首写后撤权 | 036 `RegistryAclGuard.cs L31-44`、`run_tests.ps1 L237` | 候选没真写注册表 → 内核通知不触发 → `$guard.Applied` 恒 false → F2P 必失败 |
| `GetValueKind` + `GetValue(..., DoNotExpandEnvironmentNames)` | 036 `run_tests.ps1 L22/L27`；043 | 便捷 API 会展开 `REG_EXPAND_SZ`、抹平类型 |
| `NamedPipeServerStream(Message, Asynchronous)` + 小缓冲 + `IsMessageComplete` | 021 `server.ps1 L6-L7` | Message 模式是命名管道独有 |
| 让第二进程持有同名 Event/Mutex，看候选能否操作同一对象 | 018 / 020 | 命名对象在 `Local\`/`Global\` 内核命名空间 |
| 空闲 CPU 增量否决"轮询冒充事件" | 002.1 `:590-615` | 运行时可观测，不靠扫源码 |
| 独立账号 + Job Object + 私有 window station 运行候选，并用探针自证读不到 tests | 019 `test.ps1 L37-63/L80-82`、`ExecGuard.cs` | 同时给出隔离的**负访问证明** |

### 5.1 判分基础设施：INVALID 与 FAIL 分离（R6）

照抄 019 `tests/test.ps1`：

- 基础设施异常 → 写 `invalid.txt`、**删除 `reward.txt`**、`exit 4`（L106 / L117）；
- required 集合**三方比对**：`required_testcases.json` ↔ `result.required` ↔ `result.testcases`，
  数量 / 唯一性 / 组别 / 终态任一不符即 throw（L94-100）；
- 二值分由"全 PASS"决定，并校验 `$result.score` 与之一致（L101-102）；
- 候选硬期限 + 杀进程树 + 事后无残留进程/文件校验。

### 5.2 对抗性夹具（让近似实现必然翻车）

- 文件名同时含**中文 + 空格 + 方括号**（`文件 [1].txt`）；
- **文件符号链接起一个满足 `.log` 扩展名的名字**（`filelink.log`）——专打"按扩展名收集"的实现；
- junction **指向扫描根内部**（防"只比路径前缀"的逃逸判定）；
- 属性夹具**预置 `System|Archive`**，断言 `-band 36 -eq 36`；
- 编码/BOM/属性判定走**字节与位**（`ReadAllBytes` + `ToHexString`、`GetAttributes() -band`），
  不要用 `ReadAllText`（会吞 BOM 造成假通过），读 Hidden 必须加 `-Force`。

---

## 6. 验收侧交付口径（R1）

甲方返修第 1 条：「请把**参考解和隐藏测试作为验收侧资产**一并交付，并保持对模型隔离。」

三条口径必须分清：

| 范围 | 内容 | 说明 |
|---|---|---|
| **完整本地题** | `task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/` / `source.json` | 规范标准树，`solution/**` 在此**必须存在** |
| **普通模型资产** | 参与方可见部分 | **不得**携带 `solution/**` |
| **验收侧交付包** | 完整本地题 + 隐藏测试副本 + `delivery-extras/`（元数据、证据、运行记录） | **提交给甲方质检的形态**，`solution/**` 必须在内 |

**默认提交形态 = 验收侧交付包**，且必须附：

1. `solution/reference/**`（`solve.ps1` 依赖的参考源码 —— 215/216 本次正是缺这一项）；
2. 隐藏语义测试在 `tests/` 下的副本（215/216 缺 `tests/test_*_semantics.py`，
   与 218/219 的形态不一致）；
3. 隔离的**负访问证明**（探针脚本 + 结果，形态参考 019 `GuardProbe.cs` 与
   包内 `verifier/negative_access_probe.ps1`）。

> 只在收件方**明确要求**纯参与方包（Harbor 四件套）时才导出精简形态；
> 导出后仍需在 `delivery-extras/` 留一份完整题与哈希，供甲方比对。

---

## 7. 历史包豁免口径

`--allow-legacy-exempt` + 包内 `WINDOWS_MECHANISM_EXEMPT.md` 可把 F1–F5 降级为 FLAG，
用于**不追溯改判历史样本**（甲方明文：新需求不得追溯扣旧样本）。

- **F6 永不免除**；
- 豁免生效时脚本会追加 FLAG：**打包交付前必须删除该标记文件**，否则等同于把自认句交给甲方；
- 新生产的题**不得**使用豁免。

---

## 8. 复验通过标准

| # | 标准 |
|---|---|
| 1 | `check_windows_mechanism.py` 退出码 `0`，且 `mechanisms` 每条都能在题面与 tests 中人工复定位 |
| 2 | `instruction.md` 含排他声明；包内无任何自我否认 Windows 价值的表述 |
| 3 | 每条机制至少绑定一条 **F2P** 用例，且该用例在 no-change 轮**真失败**、在 Golden 轮**真通过** |
| 4 | 环境层存在"非 Windows / 非 NTFS 必然失败"的 preflight，且该情形记为 **INVALID** 而非 0 分 |
| 5 | 验收侧交付包含 `solution/**` 与隐藏测试副本，并有隔离的负访问证据 |
| 6 | 改动题包内容后旧 `jobs/` 的 `task_checksum` 必然失效 → **整批重跑**，不得复用旧轮次 |
