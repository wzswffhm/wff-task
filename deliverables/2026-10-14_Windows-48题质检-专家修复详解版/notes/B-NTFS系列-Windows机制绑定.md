# B. NTFS 系列 —— Windows 机制绑定逆向分析

分析对象：`deliverables/2026-10-14_Windows-48题质检-专家修复详解版/extracted/` 下 5 个被评为「Windows 价值高」的样本
`031`(windows-file-attributes-003)、`007`(win-reparse-002)、`017`(windows-junction-boundary-002)、`024`(windows-ntfs-ads-003)、`037`(windows-hardlink-isolation-002)。

目的：回答「甲方说我们三道自研题（wchunk-216 / wfmt-215 / wlogseg-218）是平台无关的容器格式/CRC/流式 IO，那这些高分题到底把什么 Windows 专属机制做进了题」，并提炼可复用模板。

---

## 0. 阅读范围与方法（先说明证据边界）

**已通读**（这 5 个样本的全部文件，共 60 个，逐字节读取）：

| 题 | instruction / task.toml | environment | tests |
|---|---|---|---|
| 031 | 有 | adapter / cleanup / Dockerfile / prepare / restore / run / validate | run_tests / rubric / required_testcases / aggregate_results / judge / test.ps1 / test.bat |
| 007 | 有 | adapter / build / cleanup / Dockerfile / prepare / restore / run / validate | run_tests / test.ps1 / rubric / required_testcases / testcase_mapping.csv / aggregate_results / judge / test.bat |
| 017 | 有 | 同 031 结构 7 个文件 | 同 031 结构 |
| 024 | 有 | 同 031 结构 7 个文件 | 同 031 结构 |
| 037 | 有 | 同 017 结构 7 个文件 | 同 017 结构 |

**两条必须先说清的证据边界**（影响结论强度，避免下游误判）：

1. **extracted 里没有候选/参考实现**。`environment/workspace/`、`environment/workspace/candidate.ps1`、`solution/` 在 5 个样本里**全部不存在**（已用 `Test-Path` 逐个确认，5 题 × 4 路径 = 20 个全为 `False`）。所以本文对「prepare 如何造夹具」的结论是：**prepare 不造 Windows 夹具，只复制 candidate**；真正的 NTFS 夹具一律在 `tests/run_tests.ps1` 运行时动态构造（`fixtures-<GUID>`）。这是这批题的一个统一架构选择，也是它们能做出真实 Windows 对象的关键。
2. **环境层是模板化的，不是每题手写**。SHA256 逐个比对结果：
   - `031` 与 `024` 的 `environment/` 下 **7 个文件全部 SAME**（adapter/cleanup/Dockerfile/prepare/restore/run/validate），`tests/` 下 `aggregate_results.ps1`、`test.ps1`、`test.bat` 也 SAME；
   - `017` 与 `037` 的 `environment/` 下 **7 个文件全部 SAME**，`tests/` 下 `aggregate_results.ps1`、`test.ps1`、`test.bat` SAME；
   - 两组的 `environment/` 也有大量同名同构。
   即：**Windows 绑定强度几乎全部由「instruction + task.toml + run_tests.ps1 三个文件」承担**，环境脚本是共享骨架。这对我们复用是好消息——不需要重造环境层。

---

## 1. 总结论

**这批题把 Windows 机制做进题的公式是：用真实的 NTFS 对象当夹具（junction / symlink / ADS / 硬链接 / 属性位），再用「多个实现无法同时满足」的断言把跨平台近似解全部排掉。**

拆成四个可复制的动作：

1. **题面把验收锚定在 Windows 的数据模型名词上**，而不是行为描述。写「保留 Archive、System 以及其他属性位」（031）、「发现重解析点（例如 junction）就拒绝」（007）、「junction、目录符号链接、循环链接都必须跳过」（017）、「NTFS 备用数据流」（024）、「其他硬链接必须保留原来的内容」（037）。这些名词本身在 POSIX 侧没有对应物，题面即完成了机制声明。
2. **夹具是真的**。`mklink /J`、`New-Item -ItemType Junction`、`New-Item -ItemType SymbolicLink`、`New-Item -ItemType HardLink`、`[IO.File]::SetAttributes($p, 39)`、`[IO.File]::WriteAllText($p+':meta', ...)`。不是用一个「看起来像链接的目录」或用配置文件模拟 ADS，而是让 NTFS 真的长出这些对象。
3. **判定独立于候选**。用 `[IO.File]::GetAttributes()` 读回真实属性位并与掩码做 `-band`；用 `Get-Item -LiteralPath $p -Stream *` 独立枚举真实流；用 `[IO.File]::ReadAllBytes($p+':meta')` 直接读流字节并比对十六进制。**候选说什么不重要，文件系统上是什么才算数。**
4. **让错误实现必然翻车**。这是最关键的一招。例如 017 的 `symbolic_links_skipped` 里，文件符号链接的名字是 `filelink.log`（满足 `.log` 扩展名）。一个「只按扩展名收集文件」的跨平台近似实现会把 `filelink.log` 收进结果 → FAIL；只有真的去查重解析点属性才能通过。同理 031 的 `-band 36 -eq 36` 让「用 `attrib +h` 之外别无他法保留 System 位」的近似实现翻车。

**一个必须澄清的预期偏差**：任务书里提示我 grep 的关键词 `fsutil`、`GetFileInformationByHandle`、`FileId`、`nFileIndexHigh`、`SeBackupPrivilege`、`Get-Acl`、`:Zone.Identifier` —— **在这 5 个样本里基本不出现**。5 题全部没有 P/Invoke、没有 `fsutil`、没有 FileID 判定、没有 ACL 判定、没有 `Zone.Identifier`（024 用的是自定义流名 `meta`/`data`）。

- 037 题名叫 `hardlink-isolation`，但我通读了 `037/tests/run_tests.ps1`（42 行，全文只有 5 个用例），**没有任何 FileID / nFileIndex 断言**；它判「是否真的做了硬链接隔离」用的是**内容隔离性**（`$other` 是否还是 `'before'`）+ 替换后 `ReparsePoint` 属性位为 0。见 §3.5。
- 这些更强的写法（P/Invoke `GetFileInformationByHandle`、`fsutil hardlink create`、`FindFirstStreamW`、`Zone.Identifier`、`Get-Acl`）密集出现在**同一 extracted 目录下我负责范围之外的题**里（002.1 / 002.2 / 002.3 / 002.6 / 003 / 010 / 036 / 019）。我把它们作为「更高强度档位」放在 §4 作对照。

**结论**：这 5 题是「中等强度」的 Windows 绑定——绑定发生在**夹具与判定的对象层面**（真实 NTFS 对象），而非**系统调用/内核结构层面**（FileID、reparse tag、SDDL、特权）。对我方三题来说，先做到这一档就已经能回答案「不是平台无关」；若要冲更高分，再按 §4 上探到 FileID/reparse tag/ACL 档。

---

## 2. 对我方三道题的直接映射（推断性建议）

我方三题被判「平台无关的容器格式 / CRC / 流式 IO」——共同病根是**把机制放在了自定义格式层**（自己定的 chunk 头、自己算的 CRC、自己切的段），而没有一处依赖宿主 OS 的数据模型。按本批样本的公式，最小改造是把「存储与元数据」从自定义格式里挪到 NTFS 上：

| 我方题 | 可注入的 Windows 依赖（按本批样本已验证可行的手法） |
|---|---|
| `wfflab__wchunk-216`（分块） | 块文件用 `fsutil sparse setflag` 做成稀疏文件（§4 有现成范例）；分块索引放进所宿主文件的 ADS；块去重靠 `New-Item -ItemType HardLink` + 内容隔离判定；"分块是否指向同一份数据"用 FileID 判定 |
| `wfflab__wfmt-215`（格式/校验） | 校验和之外增加**属性位保留**断言（031 的 `-band 36 -eq 36` 可直接搬）；写入前拒绝 junction/符号链接目标（007/017 的手法）；`Zone.Identifier` 来源标记的写入与保留（§4） |
| `wfflab__wlogseg-218`（日志分段） | 分段目录扫描必须跳过重解析点（017 的 `internal_link_sort_preserve` 可直接搬）；段文件轮转后硬链接隔离（037）；同一 FileID 判定"轮转前后是同一份数据" |

---

## 3. 逐题分析

### 3.1 `031` windows-file-attributes-003 —— Windows 文件属性位保留

**机制关键词**：`[IO.FileAttributes]` 位掩码（Hidden=2 / ReadOnly=1 / System=4 / Archive=32）、位保留、`Get-Item` 读属性、PowerShell 提供程序限定路径 `FileSystem::`、字面路径（方括号不通配）、OS build 冻结。

#### 3.1.1 题面层

`031/instruction.md` 全文只有 5 行，验收锚点集中在第 1 行与第 5 行：

> **原文（instruction.md:1）**：「请修复 workspace/candidate.ps1，参数为 -Path、-Hidden、-ReadOnly。只修改指定普通文件的 Hidden 和 ReadOnly 属性，两个参数均为布尔值；**必须保留该文件已有的 Archive、System 以及其他属性**。返回对象包含 Status="updated"。**路径按字面处理，不得使用通配符**，不得改动其他文件或目录。」
>
> — 中文解释：把「改属性」这个动作的**语义边界**写死在 Windows 的位模型上。"只改 Hidden 和 ReadOnly、保留 Archive、System 以及其他属性"意味着候选不能走「先清空属性再设目标属性」的简单路径（`SetAttributes(path, Normal)` 再叠加），也不能用整组覆盖；必须做**读-改-写位运算**。"路径按字面处理，不得使用通配符"则排除了 `-Path` 走通配符展开的实现（文件名里带 `[1]` 时行为会不同）。这一句同时是 Windows 属性模型声明 + 路径语义声明。
>
> **原文（instruction.md:5）**：「真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。」
>
> — 中文解释：**显式点名了 NTFS**，并冻结了 OS build / PowerShell 版本，同时约束了改动面（只改 candidate.ps1）、网络（离线）、输出（不额外打日志）。
>
> **原文（instruction.md:3）**：「支持已有普通文件。」
>
> — 中文解释：限定输入是**已存在的普通文件**，从而把目录、重解析点、不存在路径这些分支从验收面剔除，让断言可以只盯位运算。

**是否显式点名具体 NTFS 机制**：是，但只点了文件系统名（NTFS）+ Windows 属性名词（Hidden/ReadOnly/Archive/System）。**没有点 API 名**（没写 `FileAttributes`、`GetFileAttributes`）。

**是否声明「不需要其他操作系统版本」**：**没有**。5 个样本里**都不存在**这类显式措辞。存在的是三类替代声明：(a) 题面「真实环境：…」的事实陈述；(b) `task.toml` 的结构化字段 `os="windows"` / `filesystem="NTFS"`；(c) `validate_environment.ps1` 的硬失败断言。**这是一个可以补的项**——加一句「本题只需在 Windows Server 2022 x64 build 20348 上成立，不需要也不能在 Linux/其他 Windows 版本上通过」能让「Windows 专属」从暗示变成显式要求。

#### 3.1.2 环境层

`031/environment/validate_environment.ps1` 全文（3 行）：

```powershell
$ErrorActionPreference='Stop'
if(!$IsWindows-or $PSVersionTable.PSVersion.ToString()-ne '7.5.10'){throw 'Frozen Windows PowerShell runtime required'}
if((Get-CimInstance Win32_OperatingSystem).Version-ne '10.0.20348'){throw 'Frozen Windows build required'}
```
（`031/environment/validate_environment.ps1:1-3`）

- 第 2 行：`!$IsWindows` → 在 Linux/macOS 上 `$IsWindows` 为 `$false`，**非 Windows 必然失败**，且 `-or` 后面还要求 PowerShell 版本**精确等于** `7.5.10`（用 `-ne` 而非 `-lt`，比 017/037 更严格）。
- 第 3 行：`Win32_OperatingSystem.Version` 必须等于 `10.0.20348`（Windows Server 2022），这是**只存在于 Windows 的 WMI/CIM 提供程序**调用，Linux 上直接失败。

`prepare.ps1` 的 Windows 相关点（`031/environment/prepare.ps1:3-4`）：

```powershell
if(Test-Path -LiteralPath $WorkspaceRoot){throw 'WorkspaceRoot must be a new directory'}
& (Join-Path $PSScriptRoot 'validate_environment.ps1')
```

- 第 3 行是**幂等保护**：要求目标是全新目录，防止两次 prepare 叠加。
- 第 4 行**主动调用 validate**——注意这是与 `017`/`037` 的差异（后两者 prepare 未调用 validate，见 §3.3.2），是更稳的写法。

`task.toml` 的结构化声明（`031/task.toml:19-27`）：

```toml
[environment]
os = "windows"
edition = "Windows Server 2022 Standard"
build = "10.0.20348"
architecture = "x86_64"
locale = "zh-CN"
shell = "PowerShell 7.5.10"
filesystem = "NTFS"
network_mode = "no-network"
permissions = "current user, no elevation needed"
```

- `filesystem = "NTFS"` 是**机器可读的机制声明**，配合 `permissions = "current user, no elevation needed"` 明确「不需要管理员」，排除了「靠特权才能复现」的实现依赖。
- `031/task.toml:2`：`docker_image = "mcr.microsoft.com/powershell:7.5-windowsservercore-ltsc2022"`（Windows Server Core 镜像）；`031/environment/Dockerfile:1-3` 只有 3 行，`FROM` 同上 + `WORKDIR C:/workspace` + `COPY workspace/ C:/workspace/`——**镜像本身就是 Windows 约束的载体**。
- `031/environment/adapter.toml:1`：`adapter = "native-windows"`（区别于容器/其他 adapter），`:8` `network_mode = "offline"`。

**有无「强制检查文件系统为 NTFS」**：**没有**。`031`（以及 `017`/`024`/`037`）的 validate 只检查 `$IsWindows` + build，**没有** `GetVolumeInformation` / `fsutil fsinfo volumeinfo` 之类的卷类型断言。`task.toml` 里的 `filesystem = "NTFS"` 是声明而非运行时校验。这是**一个可补强的缺口**：把工作区所在的卷真正断言成 NTFS（`(Get-Volume -DriveLetter X).FileSystemType -eq 'NTFS'` 或 `fsutil fsinfo volumeinfo`），才能杜绝「题在 ReFS/FAT32 上跑出不同结果」。

**关键点：Windows 夹具不在环境层，在验证层。** `prepare.ps1` 只做了一件事——复制候选（`031/environment/prepare.ps1:5-6`）：

```powershell
New-Item -ItemType Directory -Path $WorkspaceRoot|Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'workspace/candidate.ps1') -Destination (Join-Path $WorkspaceRoot 'candidate.ps1')
```

真正的属性位夹具、含方括号/中文的文件名，全部由 `tests/run_tests.ps1` 在运行时构造（见下）。`environment/run.ps1` 也极简（`:1-2`）：`& (Join-Path $WorkspaceRoot "candidate.ps1") @Arguments`。

#### 3.1.3 验证层（核心证据）

`031/tests/run_tests.ps1` 共 39 行，5 个用例。夹具根目录是运行期 UUID 目录（`:2`）：

```powershell
$fixtureRoot=Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))
```

**用例 1 `enable`（`:9`）——读真实属性位并对 Hidden|ReadOnly 掩码做位与**：

```powershell
$p=Join-Path $fixture '文件 [1].txt';[IO.File]::WriteAllText($p,'safe');
$r=& $candidate -Path $p -Hidden $true -ReadOnly $true;
$a=[IO.File]::GetAttributes($p);
($r.Status-eq 'updated')-and(($a-band 3)-eq 3)
```

- `[IO.File]::GetAttributes($p)` 是 **Win32 `GetFileAttributes` 的 .NET 包装**，直接读回磁盘上的属性位——这是「候选真的操作了 Windows 属性」的独立证据，而不是相信候选的返回值。
- `$a -band 3`：`3 = ReadOnly(1) | Hidden(2)`。断言两位都被置上。
- 文件名 `文件 [1].txt` 同时含**中文 + 空格 + 方括号**——方括号是 PowerShell 通配符元字符，这是对题面「路径按字面处理，不得使用通配符」的**对抗性夹具**。若候选内部用了非 `-LiteralPath` 的路径处理，此用例会失败。

**用例 2 `clear_preserve_system`（`:15`）——本题最强的一条断言，直接锁死"位保留"**：

```powershell
$p=Join-Path $fixture 'flag.txt';[IO.File]::WriteAllText($p,'safe');
[IO.File]::SetAttributes($p,[IO.FileAttributes]39);
$r=& $candidate -Path $p -Hidden $false -ReadOnly $false;
$a=[IO.File]::GetAttributes($p);
($r.Status-eq 'updated')-and(($a-band 3)-eq 0)-and(($a-band 36)-eq 36)
```

- `[IO.File]::SetAttributes($p, 39)`：**39 = Archive(32) + System(4) + Hidden(2) + ReadOnly(1)**。夹具刻意预置了 `System` 和 `Archive` 两个位。
- 断言 `($a -band 3) -eq 0`：`Hidden|ReadOnly` 两位必须被清掉。
- 断言 `($a -band 36) -eq 36`：`36 = Archive(32) + System(4)`，**两位必须原封不动保留**。
- 这条断言为什么能排除跨平台近似：一个「把属性设成目标值」的实现（例如 `SetAttributes($p, Normal)` 或按 `$Hidden/$ReadOnly` 直接拼一个新值）会连带清掉 `System`/`Archive` → `-band 36` 不等于 `36` → FAIL。**只有真正做「读现有位 → 只翻转指定位 → 写回」的实现能通过**，而这正是 Windows 属性位模型的语义。此外 `System` 位在 Windows 上是受保护属性（通常 `attrib +s` 需要相应权限，普通 API 写入行为特殊），把它放进夹具本身就带有 Windows 特异性。

**用例 3 `mixed_repeat`（`:21`）——部分保留 + 重复调用幂等**：

```powershell
[IO.File]::SetAttributes($p,[IO.FileAttributes]36);          # System|Archive
& $candidate -Path $p -Hidden $true  -ReadOnly $false|Out-Null;
& $candidate -Path $p -Hidden $false -ReadOnly $true|Out-Null;
$r=& $candidate -Path $p -Hidden $false -ReadOnly $true;
$a=[IO.File]::GetAttributes($p);
($r.Status-eq 'updated')-and(($a-band 3)-eq 1)-and(($a-band 36)-eq 36)
```

- 起点 `36 = System|Archive`（既没 Hidden 也没 ReadOnly）。
- 连续三次调用（开 Hidden、清 Hidden 开 ReadOnly、再重复一次），最终断言 `($a -band 3) -eq 1`：`1 = ReadOnly`，即 **Hidden 必须已清、ReadOnly 必须还在**；同时 `-band 36 -eq 36` 保留 System|Archive。
- 这是**三次调用后的终态断言**，同时覆盖幂等（第三次与第二次参数相同）与"两个位互不干扰"。

**用例 4 `provider_qualified`（`:27`）——PowerShell 提供程序限定路径**：

```powershell
$providerPath='FileSystem::'+$p;
$r=& $candidate -Path $providerPath -Hidden $true -ReadOnly $false;
$a=(Get-Item -LiteralPath $providerPath -Force).Attributes;
($r.Status-eq 'updated')-and(($a-band 2)-ne 0)-and(($a-band 1)-eq 0)
```

- `FileSystem::C:\...` 是 **PowerShell 提供程序限定路径**语法。夹具把带前缀的路径喂给候选，要求它照常工作——这排除了「用字符串操作硬拼 `C:\` 前缀」的实现。
- 读回改用 `Get-Item -LiteralPath ... -Force` 的 `.Attributes` 属性（与 `[IO.File]::GetAttributes` 是另一条独立读取路径），`:Force` 是必须的，否则 `Get-Item` 在 Hidden 文件上会取不到。
- 断言 `-band 2 -ne 0`（Hidden 已置）、`-band 1 -eq 0`（ReadOnly 未置）。

**用例 5 `contents_neighbors`（`:33`，P2P）——不越界**：

```powershell
$before=[IO.File]::GetAttributes($q);
& $candidate -Path $p -Hidden $false -ReadOnly $false|Out-Null;
([IO.File]::ReadAllText($q)-eq 'safe')-and([IO.File]::ReadAllText($p)-eq 'target')-and([IO.File]::GetAttributes($q)-eq $before)
```

- 同目录邻居文件 `keep.txt` 的内容与**属性位**都必须与调用前完全一致（注意是 `-eq $before` 做整值相等，比位掩码更严格）。

**基础设施失败与候选失败被严格分离**（`:9`、`:15`…每个用例同一模式）：

```powershell
catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
```

- 只有 `Infrastructure:` 前缀的异常才记 `ERROR` → 最终 `validity='INVALID'`、`score=$null`、`exit 2`（`:37-39`）。夹具造不出来（例如在非 NTFS 卷上 `SetAttributes(39)` 后位没保住）**不会**被冤枉成候选失败。这是「平台无关」判定里最容易被忽略但极重要的一环。
- 另一处精细设计（`:9`）：`$passed=& { ... }` 用脚本块收集返回值，再 `if(@($passed).Count-eq 1-and $passed-eq $true)`——**要求脚本块恰好返回一个 `$true`**，避免候选的额外输出（题面要求"不输出额外日志"）污染判定。

#### 3.1.4 夹具清理（含 031 的一个小瑕疵）

清理分两层。

**层一：测试内部，先复位属性位再删**（`031/tests/run_tests.ps1:3`）：

```powershell
function Clear-Fixtures([string]$Path){if(Test-Path -LiteralPath $Path){Get-ChildItem -LiteralPath $Path -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $Path -Recurse -Force}}
```

- 这是**处理属性位夹具的必备步骤**：`-Force` 遍历（`-Force` 让 Hidden 文件也被枚举到）→ 逐个 `SetAttributes(..., Normal)` **清掉 ReadOnly/Hidden/System** → 再 `Remove-Item -Recurse -Force`。因为 ReadOnly 文件在部分删除路径上会失败，**不复位属性位就会残留夹具**。
- 幂等：函数首行 `Test-Path` 守卫，配合 try/finally（`:5`\~`:36` 的 `try { ... } finally {Clear-Fixtures $fixtureRoot}`），无论用例如何失败都会清理，且重复调用无害。

**层二：环境清理脚本，拒绝卷根**（`031/environment/cleanup.ps1:1-4`）：

```powershell
param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop';$full=[IO.Path]::GetFullPath($WorkspaceRoot)
if($full-eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}
if(Test-Path -LiteralPath $full){Get-ChildItem -LiteralPath $full -Recurse -File -Force|ForEach-Object{[IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal)};Remove-Item -LiteralPath $full -Force -Recurse}
```

- `[IO.Path]::GetPathRoot($full)` 比较 → **如果传入的是 `C:\` 这种卷根就直接抛异常拒绝**。这是幂等之外的第二重「防呆」：宁可失败也不做破坏性递归删除。
- `restore.ps1`（`031/environment/restore.ps1:1-2`）= cleanup + prepare 串联，`cleanup.ps1` 的 `Test-Path` 守卫保证「首次 restore（还没 workspace）→ 直接 prepare」也成立，即**幂等**。
- 小瑕疵（如实记录）：每个用例都有一对注册表清理代码，`$reg='Software\OutsideHarborBench\'+GUID`（`:7`）在 `finally{[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)}`（`:10`）里删除，但 **`$reg` 在本题中从未被写入过任何键**——这是从注册表类题目继承的模板残留代码。另外 `provider_qualified` 用例里写的是 `'Software\\OutsideHarborBench\\'`（`:25`，单引号内是**双**反斜杠），与其余用例的单反斜杠不一致；因为 `DeleteSubKeyTree($reg, $false)` 的第二个参数 `throwOnMissingSubKey=$false`，键不存在也不抛异常，所以无功能影响。

---

### 3.2 `007` win-reparse-002 —— 重解析点安全复制（C# 编译型题）

**机制关键词**：junction（`cmd /c mklink /J`）、reparse point 检测、NTFS 同一卷约束、preflight（写入前全量校验）、`.NET Framework csc.exe` 编译、`icacls` 账号权限隔离、退出码协议。

#### 3.2.1 题面层

`007/instruction.md` 共 7 行，是本批里**唯一不含「真实环境：…」声明行**的题（差异点，见 3.2.2）。

> **原文（instruction.md:1、3）**：「# 安全复制普通目录」／「请修改 `src/` 里的 WinTask.exe。它接收源目录和目标目录，把源目录中的普通文件按相对路径复制过去，并保留文件的最后写入时间。」
>
> — 中文解释：这是题面标题（第 1 行）与任务概述（第 3 行）。"普通文件"是关键词——它把 ADS、重解析点等非普通对象排除在复制范围外，为第 5 行的拒绝语义铺垫。
>
> **原文（instruction.md:5）**：「源目录或目标目录的任何位置只要发现重解析点（例如 junction），就要在写入目标前直接拒绝；拒绝时不能创建或改动目标中的任何文件。源目录和目标目录必须位于同一个 NTFS 卷上，普通空目录、嵌套目录和普通文件仍要正常复制。」
>
> — 中文解释：**这一句是本题的机制核心，包含三个 Windows 专属要求**：(1)「重解析点」是 NTFS/Windows 的对象概念，明确括注 junction 给出具体机制名；(2)「在**写入目标前**直接拒绝」要求 **preflight 语义**——必须先完成全量校验再落盘，排除"边复制边发现"的实现；(3)「必须位于同一个 NTFS 卷上」是卷/文件系统约束，对应 Windows 的卷挂载与卷序列号概念。同时「拒绝时不能创建或改动目标中的任何文件」把「拒绝」从"返回错误码"加码到"零副作用"。
>
> **原文（instruction.md:7）**：「命令行保持为 `WinTask.exe <源目录> <目标目录>`。参数错误或安全校验失败时返回 2，并在标准输出输出 `{"status":"error","kind":"validation"}`；普通 I/O 失败返回 3；成功返回 0 并输出 `{"status":"ok"}`。不要增加网络、服务或额外开关。」
>
> — 中文解释：把**契约固化成进程级退出码 + stdout JSON**。这一点很重要：它把验证从"读候选的返回值对象"变成"读真实进程退出码与 stdout"，使验证层可以走黑盒（`tests/test.ps1:11` 的 `Invoke-App`），从而让验证完全不依赖候选内部实现。

**是否显式点名具体 NTFS 机制**：**是，且是本批最明确的一题**——「重解析点（例如 junction）」+「同一个 NTFS 卷」。`task.toml` 里还有结构化标签（见下）。

**是否声明「不需要其他操作系统版本」**：没有显式措辞；但 `task.toml` 的 `os = "windows"`（`007/task.toml:27`）与 Windows 容器镜像是最强约束。

#### 3.2.2 环境层

`007/task.toml:10-15` 的元数据把机制标签化了：

```toml
[metadata]
task_id = "win-reparse-002"
task_version = "0.1.0"
category = "windows-filesystem"
difficulty = "hard-candidate"
tags = ["windows", "ntfs", "reparse-point", "junction", "copy"]
```

- `category = "windows-filesystem"` + `tags` 里 **`ntfs` / `reparse-point` / `junction`** 三个机制词，使这道题在题包索引层面就被标记为 Windows 机制题。对比 031/017/024/037，它们的 `task.toml` **没有 `tags` 字段**——这是 007 独有、且值得抄的一点。

`007/environment/Dockerfile` 是本批唯一做了**真实权限隔离**的环境文件（`:8-20`）：

```dockerfile
RUN net user BenchAgent /add; `
    if ($LASTEXITCODE -ne 0) { throw 'Agent account creation failed' }; `
    New-Item -ItemType Directory -Force C:\agenttmp | Out-Null; `
    icacls C:\testbed /grant 'BenchAgent:(OI)(CI)RX'; `
    if ($LASTEXITCODE -ne 0) { throw 'Workspace ACL setup failed' }; `
    icacls C:\testbed\src /grant 'BenchAgent:(OI)(CI)M'; `
    ...
    icacls C:\testbed\bin /grant 'BenchAgent:(OI)(CI)M'; `
```
（`007/environment/Dockerfile:8-20`，摘录）

- `net user BenchAgent /add` + `icacls ... 'BenchAgent:(OI)(CI)RX'`：**创建真实本地账号并授予继承式 ACL**（`(OI)(CI)` = 对象继承/容器继承，`RX` = 读+执行，`M` = 修改）。配合 `task.toml:19-23` 的 `[agent] user="BenchAgent"` / `[verifier] user="ContainerAdministrator"`，构成「考生账号权限受限、验证者权限完整」的 Windows 安全模型。
- 每个 `icacls` 后都紧跟 `if ($LASTEXITCODE -ne 0) { throw ... }`——**ACL 设置失败即镜像构建失败**，不允许静默降级。这是"夹具造不出来就别出题"的正确态度。
- `Dockerfile:4`：`ENV WINBENCH_DISPOSABLE_CONTAINER="1"`，配合 `:18` 构建后删掉 bin 再重新授权，`:21` 的 `CMD` 是 `while ($true) { Start-Sleep -Seconds 3600 }`（容器保活等待注入）。
- `Dockerfile:2` 用了带 **digest 固定**的基础镜像（`@sha256:3b38924c...`），比 031 的 `:7.5-windowsservercore-ltsc2022` 标签固定更严格——镜像层不可漂移。

`007/environment/build.ps1` 把 Windows 专属编译器写死在路径上（`:6-10`）：

```powershell
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw 'Required .NET Framework x64 C# compiler missing' }
$sources = @(Get-ChildItem (Join-Path $root 'src') -Filter '*.cs' -Recurse | ForEach-Object { $_.FullName })
if ($sources.Count -eq 0) { throw 'No C# source files' }
& $csc /nologo /codepage:65001 /langversion:5 /target:exe /platform:x64 /optimize+ /r:System.Web.Extensions.dll ('/out:' + (Join-Path $bin 'WinTask.exe')) $sources
```

- `$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe` 是 **.NET Framework 4.x 的 x64 编译器**，只在 Windows 存在；`:7` 显式断言它存在，否则抛「Required .NET Framework x64 C# compiler missing」→ **非 Windows 必然构建失败**。
- `/platform:x64` + `/langversion:5` 锁定了目标架构与语言级别（C# 5，无 async/using static 等新语法糖，便于确定性编译）。
- 验证层 `007/tests/test.ps1:6` 会**重新编译**候选：`& 'C:\testbed\build.ps1' *> (Join-Path $logs 'candidate-build.log')`，`:7` 编译失败直接 `throw 'candidate build failed'`——即候选必须留下可编译的源码，而不是提交一个二进制。

`007/environment/validate_environment.ps1:1-4` 本身很弱（只查 `build.ps1`、`src` 存在），**没有** `$IsWindows` 检查，**没有** build 号检查。这是 007 相对 031/017 的**弱项**：它的 Windows 依赖靠 Dockerfile 的 `FROM` + `csc` 路径隐含保证，而没有运行时自证。同样 `007/environment/prepare.ps1:3-5` 也只是「workspace 存在 + 调 build.ps1」。

#### 3.2.3 验证层（核心证据）

`007/tests/test.ps1` 共 22 行，6 个用例。它自己实现了 junction 的创建与删除两个辅助函数（`:12-13`）：

```powershell
function Junction([string]$link,[string]$target) { New-Item -ItemType Directory -Force $target | Out-Null; & cmd.exe /c mklink /J $link $target | Out-Null; Assert ($LASTEXITCODE -eq 0) 'junction creation failed' }
function Remove-Junction([string]$link) { if (Test-Path $link) { & cmd.exe /c rmdir $link | Out-Null } }
```

- `cmd.exe /c mklink /J` 是**最底层、最确定**的 junction 创建方式（`mklink` 是 cmd 内建命令，`/J` 建 junction）；创建后立刻断言退出码为 0，**夹具造不出来就是基础设施失败**。
- `Remove-Junction` 用 **`cmd /c rmdir`** 而非 `Remove-Item -Recurse` —— **删 junction 必须只删链接本身**。`rmdir`（不带 `/S`）删目录链接不会跟进目标，这是干净的做法。对照 §3.5 与 §5.5 的「常见坑」。
- 调用方式是黑盒的（`:11`）：

```powershell
function Invoke-App([string[]]$arguments) { $global:LASTEXITCODE=0; $text = (& $exe @arguments 2>&1 | Out-String).Trim(); [pscustomobject]@{ Code=[int]$LASTEXITCODE; Text=$text } }
```

- 直接把 `C:\testbed\bin\WinTask.exe` 当进程调，收集**真实退出码**与 stdout/stderr 合并文本。判定完全基于题面第 7 行的契约。

三个 F2P 用例（`:18-20`）逐条摘录，它们是「真的检测了重解析点」的全部证据：

```powershell
Case 'source_junction_rejected' 'F2P' { Reset $root; $src=Join-Path $root 'src'; $dst=Join-Path $root 'dst'; New-Item -ItemType Directory -Force $src | Out-Null; Junction (Join-Path $src 'linked') (Join-Path $root 'outside'); $r=Invoke-App @($src,$dst); Assert ($r.Code -eq 2) 'source junction accepted'; Assert (-not (Test-Path $dst)) 'destination was created' }
```
（`007/tests/test.ps1:18`）

- 夹具：在**源目录里**建 junction `src\linked` → `root\outside`。
- 断言 1：退出码必须是 `2`（题面规定的校验失败码）。**若候选不检测重解析点**，它会开心地跟进 junction 并把 `outside` 的内容复制过去、返回 0 → FAIL。
- 断言 2：`Assert (-not (Test-Path $dst))`——**目标目录根本不能被创建**。这把"拒绝"从"返回错误码"加码到"零副作用"，是题面第 5 行「拒绝时不能创建或改动目标中的任何文件」的直接落地。

```powershell
Case 'destination_junction_rejected' 'F2P' { ... Set-Content (Join-Path $src 'new.txt') 'new'; Junction $dst (Join-Path $root 'outside'); $r=Invoke-App @($src,$dst); Assert ($r.Code -eq 2) 'destination junction accepted'; Assert (-not (Test-Path (Join-Path $root 'outside\new.txt'))) 'wrote through junction'; Remove-Junction $dst }
```
（`007/tests/test.ps1:19`）

- 夹具：**目标目录本身**是 junction，指向 `root\outside`（源里有一个 `new.txt`）。
- 断言 2：`Assert (-not (Test-Path (Join-Path $root 'outside\new.txt'))) 'wrote through junction'`。中文意思是「不得写穿 junction」——如果候选没检测目标侧，它会把 `new.txt` 写到 junction 背后的真实目录里去。**这条断言只有 junction 这种机制才能构造出来**，是本题最强的 Windows 绑定证据。
- 用例末尾**立刻** `Remove-Junction $dst` 清理链接（不等外层 Reset），因为外层 `Reset` 用的是 `Remove-Item -Recurse -Force`（`:10`），在 Windows PowerShell 5.1 下对 junction 有跟进删除目标内容的风险（见 §5.5）。

```powershell
Case 'preflight_no_partial_copy' 'F2P' { Reset $root; ... New-Item -ItemType Directory -Force $dst | Out-Null; Set-Content (Join-Path $dst 'sentinel.txt') 'keep'; Junction (Join-Path $src 'bad') (Join-Path $root 'outside'); $r=Invoke-App @($src,$dst); Assert ($r.Code -eq 2) 'bad source accepted'; Assert ((Get-Content (Join-Path $dst 'sentinel.txt') -Raw).Trim() -eq 'keep') 'destination changed' }
```
（`007/tests/test.ps1:20`）

- 夹具：目标**已存在**且有 `sentinel.txt`='keep'；源里埋了一个 junction。
- 断言 2：哨兵文件内容必须原样保留。这排除了「先复制已通过校验的部分文件、再在遇到 junction 时报错」的**部分写入**实现。用例名 `preflight_no_partial_copy` 直接点出 preflight 语义。
- 三条用例组合起来，构成一个只有「递归遍历时逐项检查 `FileAttributes.ReparsePoint`、且在写任何东西之前完成全量预检」的实现才能全部通过的判定集。

P2P 用例（`:15-17`）是正常路径回归：`copy_tree`（嵌套目录内容一致）、`empty_tree`（空目录也要建出目标）、`timestamp_preserved`（用 `[IO.File]::SetLastWriteTimeUtc($f, $stamp)` 预置 7 分钟前的时间戳，复制后 `[Math]::Abs(...TotalSeconds) -lt 3` 容差断言）。

**判定与分数的封装**（`:21`）：

```powershell
$score = if (@($cases | Where-Object status -ne 'PASS').Count -eq 0) { 1 } else { 0 }; $result=[ordered]@{validity='VALID';score=$score;required=$required;testcases=$cases}; $result | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $logs 'results.json') -Encoding UTF8; [IO.File]::WriteAllText((Join-Path $logs 'reward.txt'),[string]$score,[Text.Encoding]::ASCII); exit 0
```

- 全 PASS → 1，任一 FAIL → 0（binary）。
- `$required`（`:8`）是硬编码的用例 id 列表，与 `rubric.json` / `required_testcases.json` / `testcase_mapping.csv` **四份**互相印证，`tests/aggregate_results.ps1:7-9` 做二次校验（要求 `cases.Count -eq required.Count`、id 唯一、状态只能 PASS/FAIL），任一不符即 `{"validity":"INVALID","score":null}` + `exit 2`。这是**防篡改**设计：候选即使能影响 `results.json`，也得同时骗过 aggregate 层的数量与 id 校验。
- 注意 `exit 0`：**测试脚本自己总是退出 0**，真正的判定结果走 `reward.txt` / `results.json`，由 aggregate 层与 judge 层消费。这与 031/017 系列「测试脚本用退出码 0/1/2 表达 PASS/FAIL/INVALID」（见 §3.1.3）是不同的机制，属于题包版本差异（007 是 schema 1.3，031 系列是 schema 1.0）。
- **弱项（如实记录）**：007 的 `Case` 函数（`:14`）只有 `PASS`/`FAIL` 两种状态，**没有** 031 系列那种 `Infrastructure:` → `ERROR` → `INVALID` 的分离。若夹具创建失败（例如 `mklink /J` 在非 NTFS 上失败），会被记成候选 FAIL 而不是基础设施 INVALID。这是 007 可改进的点。

#### 3.2.4 夹具清理

- 用例内部（`007/tests/test.ps1:10`）：`function Reset([string]$path) { Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force $path | Out-Null }`——**幂等**（`SilentlyContinue` + `-Force` 重建）。
- 脚本入口（`:5`）：`Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue` 先清空本次夹具根。
- junction 专项（`:13`+`:19`）：`Remove-Junction` 用 `cmd /c rmdir`，且 `destination_junction_rejected` 用例在末尾**立即**调用。
- 环境层（`007/environment/cleanup.ps1:1-3`）：

```powershell
param([string]$Scratch = 'C:\bench-fixtures')
$ErrorActionPreference = 'SilentlyContinue'
if (Test-Path $Scratch) { Remove-Item $Scratch -Recurse -Force }
```

- `$Address` 默认 `C:\bench-fixtures` 与 `test.ps1:3` 的 `$root = 'C:\bench-fixtures\reparse'` **前缀一致**——即环境清理能覆盖测试留下的全部夹具。`SilentlyContinue` + `Test-Path` 守卫保证幂等。
- `007/environment/restore.ps1:1-4`：先删 `bin` 再重新 `build.ps1`，也是幂等重置（对应"重新编译候选取干净基线"）。

---

### 3.3 `017` windows-junction-boundary-002 —— junction 与 symlink 的枚举边界

**机制关键词**：`New-Item -ItemType Junction`、`New-Item -ItemType SymbolicLink`（目录链接 + 文件链接）、循环链接（自指）、**内部链接也要跳过**、反斜杠路径、OrdinalIgnoreCase 排序、大小写不敏感扩展名。

#### 3.3.1 题面层

> **原文（instruction.md:1）**：「请修好 workspace/candidate.ps1，用 -Root 扫描一个本地 NTFS 目录，返回一个包含 Files 属性的对象。Files 是根目录下所有普通 .log 文件的相对路径数组，扩展名不区分大小写，路径使用反斜杠，按 OrdinalIgnoreCase 排序。需要递归普通子目录，文件名按字面处理。目录树中可能存在 junction、目录符号链接、循环链接；**所有重解析点都必须跳过，包括指向根目录内部的链接**。不能访问链接目标或改动任何文件。空目录返回空数组，Root 自身必须是一个普通目录。」
>
> — 中文解释：这段是「枚举边界」的完整规格，Windows 机制密集：
> - 「NTFS 目录」「junction」「目录符号链接」「循环链接」「重解析点」——**四种机制名词连续出现**，是本批 5 题里机制词最密的一句。
> - 「**所有重解析点都必须跳过，包括指向根目录内部的链接**」——这句是精髓。直觉上「指向根内部的链接」不算逃逸、看似可以跟随，但题面明确要求**也跳过**。这排除了「只防逃逸（检查目标是否在根外）」的实现，要求候选判定**重解析点属性本身**而不是判定链接目标。这是本题与我方"平台无关"题最大的差别：判定依据必须是「这个目录项是不是重解析点」，而不是「它指向哪里」——前者是 NTFS 对象属性，后者是路径逻辑。
> - 「不能访问链接目标」——连读都不许读（防止把链接当普通目录打开）。
> - 「路径使用反斜杠，按 OrdinalIgnoreCase 排序」「扩展名不区分大小写」——Windows 路径与大小写语义（`OrdinalIgnoreCase` 是 .NET 的 Windows 风格文化无关忽略大小写比较）。
>
> **原文（instruction.md:3）**：「运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。」
>
> — 中文解释：显式 NTFS 声明 + 版本冻结 + 改动面/网络/输出约束。

**是否显式点名具体 NTFS 机制**：是，而且点名了 **4 类**（junction / 目录符号链接 / 循环链接 / 重解析点）。

**是否声明「不需要其他操作系统版本」**：无显式措辞（同 031）。

#### 3.3.2 环境层

`017/environment/validate_environment.ps1:1-5`（这是 017/037 共享的骨架，比 031 宽松一档）：

```powershell
$ErrorActionPreference='Stop'
if(!$IsWindows){throw 'Windows required'}
if($PSVersionTable.PSVersion -lt [version]'7.5'){throw 'PowerShell 7.5 required'}
$os=Get-CimInstance Win32_OperatingSystem
if($os.Version-ne '10.0.20348'){throw 'Windows Server 2022 build 20348 required'}
```

- 第 2-4 行 = 与 031 同构的三重检查（`$IsWindows` / PS 版本 / build 20348），但 PS 版本用 `-lt [version]'7.5'`（下限）而非 031 的精确 `-ne '7.5.10'`。
- 第 3 行的 `[version]` 类型转换是**版本号比较**的正确写法（字符串比较会得到 `7.10 < 7.5` 的错误结论）——这个细节值得抄。
- `task.toml:19-27` 同 031：`os="windows"` / `build="10.0.20348"` / `filesystem="NTFS"` / `network_mode="no-network"` / `permissions="current user, no elevation needed"`。
- `prepare.ps1:1-5` 与 031 几乎相同（新目录保护 + 复制 candidate），**但没有调用 `validate_environment.ps1`**（对比 `031/environment/prepare.ps1:4`）。这是 017/037 的弱项：`validate` 只由适配器框架在其他阶段调用，prepare 自身不保证前置条件。**建议抄 031 的写法**，在 prepare 首行调用 validate。
- 同样**没有** NTFS 卷类型断言。而 017 的语义完全依赖 NTFS（junction 只在 NTFS 上是这种形态）——这是最该补 NTFS 校验的一题。

#### 3.3.3 验证层（核心证据）

`017/tests/run_tests.ps1` 共 48 行，6 个用例。3 个 F2P 用例全部围绕真实重解析点。

**用例 `junction_skipped`（`:17`）——外部 junction + 自指循环 junction**：

```powershell
$root=Join-Path $fixture 'root';$outside=Join-Path $fixture 'outside';
New-Item -ItemType Directory -Path $root,$outside -Force|Out-Null;
[IO.File]::WriteAllText((Join-Path $root 'real.log'),'r');
[IO.File]::WriteAllText((Join-Path $outside 'secret.log'),'s');
New-Item -ItemType Junction -Path (Join-Path $root 'external') -Target $outside|Out-Null;
New-Item -ItemType Junction -Path (Join-Path $root 'loop') -Target $root|Out-Null;
$r=& $candidate -Root $root;
(@($r.Files)-join '|')-eq 'real.log'
```
（`017/tests/run_tests.ps1:17`，摘录整理）

- 两个夹具：`root\external` → `outside`（外部，诱饵 `secret.log`）与 `root\loop` → `root`（**自指循环**）。
- 断言结果必须是 `'real.log'`（用 `|` 连接后做整串相等，比逐项比较更严格）。
- **两个失效模式同时被堵**：不检测重解析点 → 会枚举到 `secret.log`（多出项，FAIL）；不防循环 → 会无限递归或重复枚举（FAIL/超时）。
- 用 `New-Item -ItemType Junction` 而非 `mklink`：这是 **PowerShell cmdlet**，在 Linux 上该 `-ItemType` 不存在 → **夹具层就构成了非 Windows 必然失败**。

**用例 `internal_link_sort_preserve`（`:29`）——本题最强的一条，同时验 5 件事**：

```powershell
$root=Join-Path $fixture 'root';$inner=Join-Path $root 'inner';
New-Item -ItemType Directory -Path $inner -Force|Out-Null;
[IO.File]::WriteAllText((Join-Path $root 'z.log'),'z');
[IO.File]::WriteAllText((Join-Path $root 'A.LOG'),'a');
[IO.File]::WriteAllText((Join-Path $inner 'c.LoG'),'c');
[IO.File]::WriteAllText((Join-Path $root 'ignore.log.txt'),'n');
New-Item -ItemType Junction -Path (Join-Path $root 'alias') -Target $inner|Out-Null;
$r=& $candidate -Root $root;
(@($r.Files)-join '|')-eq 'A.LOG|inner\c.LoG|z.log' -and
[IO.File]::ReadAllText((Join-Path $root 'z.log'))-eq 'z' -and
[IO.File]::ReadAllText((Join-Path $root 'A.LOG'))-eq 'a' -and
[IO.File]::ReadAllText((Join-Path $inner 'c.LoG'))-eq 'c'
```
（`017/tests/run_tests.ps1:29`，摘录整理）

一条断言里塞进了 5 个验收点：

1. **内部链接必须跳过**：`alias` → `root\inner`，指向根**内部**。若跟随，结果里会出现 `alias\c.LoG`（或 `c.LoG` 重复），整串就不等于期望值。这直接落地题面「包括指向根目录内部的链接」。
2. **排序是 OrdinalIgnoreCase**：期望顺序 `A.LOG` → `inner\c.LoG` → `z.log`。注意 `A.LOG`（大写 A）排在 `inner`（小写 i）**之前**——这正是 OrdinalIgnoreCase 的行为（按不区分大小写的码点顺序：'a' < 'i' < 'z'）。若候选用了区分大小写的 Ordinal（大写字母码点小于小写，'A'=65 < 'i'=105，这里恰好也成立）或文化相关排序，在别的数据上会跑偏；用 `A.LOG` 与 `inner` 这个组合就是为了把排序规则钉死。
3. **大小写不敏感的扩展名**：夹具里同时有 `.LOG`、`.LoG`、`.log`（在 `z.log`）三种写法，都必须被收进结果。
4. **扩展名必须精确匹配**：`ignore.log.txt` 不能被收进来（`.txt` 是真实扩展名）。
5. **不能访问链接目标、不能改文件**：四个文件内容逐一读回校验（`z`/`a`/`c` 原样）。

**用例 `symbolic_links_skipped`（`:41`）——把「只按扩展名匹配」的近似实现钉死**：

```powershell
$root=Join-Path $fixture 'root';$outside=Join-Path $fixture 'outside';
New-Item -ItemType Directory -Path $root,$outside|Out-Null;
$secret=Join-Path $outside 'secret.log';[IO.File]::WriteAllText($secret,'safe');
[IO.File]::WriteAllText((Join-Path $root 'real.log'),'real');
New-Item -ItemType SymbolicLink -Path (Join-Path $root 'dirlink') -Target $outside|Out-Null;
New-Item -ItemType SymbolicLink -Path (Join-Path $root 'filelink.log') -Target $secret|Out-Null;
$r=& $candidate -Root $root;
(@($r.Files)-join '|')-eq 'real.log' -and [IO.File]::ReadAllText($secret)-eq 'safe'
```
（`017/tests/run_tests.ps1:41`，摘录整理）

- 两个夹具：**目录符号链接** `dirlink` → `outside`，以及**文件符号链接** `filelink.log` → `outside\secret.log`。
- `filelink.log` 是这个用例的核心陷阱：**它的名字满足 `.log` 扩展名**。一个「递归枚举 + 按扩展名过滤」的普通实现（在任何 OS 上都成立的那种）会把 `filelink.log` 收进结果 → 整串变成 `filelink.log|real.log` → FAIL。**只有真的去读目录项的 `ReparsePoint` 属性位并跳过，才能得到 `real.log`。** 这是本批 5 题里我最欣赏的一条判定——它用一个"看起来完全正常的文件名"把跨平台近似实现逼到死角。
- 同时断言 `secret.log` 内容仍是 `'safe'`（不能访问/改动链接目标）。注意 `New-Item -ItemType SymbolicLink` 在 Windows 上创建符号链接通常需要**开发者模式或 SeCreateSymbolicLinkPrivilege**——这是又一层 Windows 专属前提（虽然 `task.toml` 写的是 `no elevation needed`，此处存在张力，值得出题时验证容器内可创建成功，否则会退化成 Infrastructure 失败）。

另 3 个 P2P 用例：`recursive_literal`（`:11`，`[a].LOG` 方括号字面量 + `子目录` 中文目录 + 递归）、`empty_no_mutation`（`:23`，空目录返回 0 项且 `keep.txt` 未动）、`empty_array_shape`（`:35`，空结果必须是**非 null 的空数组**——`$null-ne $r.Files -and @($r.Files).Count-eq 0`，这条防的是"用 `$null` 表示空"，是 API 形状契约）。

**判定与封装**（`:45-48`）：与 031 同构——`ERROR` 前缀 → `INVALID`/`score=$null`/`exit 2`；否则全 PASS → 1。`:46` 输出里同时给了 `required` 和 `testcases` 两个同值字段（`:46`），是兼容不同 judge 版本的痕迹。

#### 3.3.4 夹具清理

- 测试内部（`017/tests/run_tests.ps1:44`）：`finally { if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Recurse -Force} }`——`Test-Path` 守卫保证幂等。
- 环境层（`017/environment/cleanup.ps1:1-4`）：

```powershell
param([Parameter(Mandatory)][string]$WorkspaceRoot)
$full=[IO.Path]::GetFullPath($WorkspaceRoot)
if($full-eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}
if(Test-Path -LiteralPath $full){Remove-Item -LiteralPath $full -Force -Recurse}
```

- 有**卷根拒绝**（第 3 行），幂等靠 `Test-Path` 守卫。
- **弱项：清理 junction/symlink 的方式不够稳**。这里直接 `Remove-Item -Recurse -Force`，**没有**先删链接、也**没有**先复位属性位（对比 §3.1.4 的 `Clear-Fixtures` 会先 `SetAttributes(..., Normal)`）。对一个**核心夹具就是 junction/symlink 的题**，这是明显的清理风险点——若 `Remove-Item -Recurse` 在某个 PowerShell 版本上跟进链接，会删掉链接目标的真实内容。007 的 `cmd /c rmdir` 是更稳的做法，应当并入模板（见 §5.4 与 §5.5）。

---

### 3.4 `024` windows-ntfs-ads-003 —— NTFS 备用数据流（ADS）

**机制关键词**：NTFS ADS、`路径:流名` 语法、`Get-Item -Stream *` 枚举、UTF-8 无 BOM、空流 vs 流不存在、幂等 Remove。

#### 3.4.1 题面层

> **原文（instruction.md:1）**：「请修复 workspace/candidate.ps1，管理当前用户可写普通文件的 **NTFS 备用数据流**。参数为 -Path、-Stream、-Action Set|Get|Remove、-Value。Set 写入 **UTF-8 无 BOM** 文本并返回 Status="set"；Get 返回 Status="found"、Value，不存在返回 Status="missing"；Remove 幂等返回 Status="removed" 或 "missing"。**主文件内容、其他数据流和文件名必须保持不变，不得把数据流内容写进主文件**。」
>
> — 中文解释：这是本批里**机制点得最直白的一题**——开篇即「NTFS 备用数据流」，直接点名 NTFS 唯一（在主流文件系统中）的 ADS 特性。
> - 「Set 写入 UTF-8 无 BOM 文本」：编码契约精确到 BOM 层面（验证层用十六进制比对，见 3.4.3）。
> - 「Get 返回 found + Value，不存在返回 missing」：把「流存在但为空」与「流不存在」区分为两种状态。
> - 「Remove 幂等返回 removed 或 missing」：显式幂等契约。
> - 「**主文件内容、其他数据流和文件名必须保持不变，不得把数据流内容写进主文件**」：这是**负面约束**——禁止"把 ADS 当普通文件读写"的近似实现（例如把流内容 append 到主文件末尾再解析）。文件名不变则禁止"改名后重建"这种偷懒实现（改名会破坏身份）。
>
> **原文（instruction.md:3）**：「Path 指向已有普通文件；Stream 是非空、**不含冒号和目录分隔符**的自定义流名称。空 Value 表示存在的空数据流。Set 覆盖旧内容，删除后 Get 返回 missing。」
>
> — 中文解释：「不含冒号和目录分隔符」是 **ADS 命名空间的真实约束**——因为 `:` 是 ADS 的分隔符（`file.txt:stream`）、`\` 是路径分隔符；若允许流名含 `:`，`路径:流名` 的拼接就会产生歧义。这条把 ADS 的语法约束写进了题面。「空 Value 表示存在的空数据流」再次强调空流 ≠ 无流。
>
> **原文（instruction.md:5）**：「真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。」
>
> — 中文解释：与 031 逐字同构的环境声明。

**是否显式点名具体 NTFS 机制**：**是，最直接的一题**（NTFS 备用数据流 + 流名语法约束）。
**是否声明「不需要其他操作系统版本」**：无显式措辞。但注意——ADS 在 Linux 上（`ntfs-3g`、`xattr` 模拟）存在部分近似，所以这题**特别需要**那句显式声明 + 卷类型断言来杜绝「用 xattr 模拟 ADS 也算过」。

#### 3.4.2 环境层

`024` 的 `environment/` 下 **7 个文件与 `031` 逐字节相同**（SHA256 全部 SAME，已确认）。因此：

- `validate_environment.ps1` 同 031：`$IsWindows` + `PSVersion -ne '7.5.10'` + `Win32_OperatingSystem.Version -ne '10.0.20348'` → **非 Windows 必然失败**。
- `task.toml:25` `filesystem = "NTFS"`；`:27 permissions="current user, no elevation needed"`。
- `prepare.ps1` 同 031（新目录保护 + **调用 validate** + 复制 candidate）。
- **没有 ADS 能力探测**。这是本题最值得补的缺口：validate 只证明"是 Windows Server 2022"，不证明"工作区卷支持 ADS"。在同一批样本里，`002.6` 就做了这件事（见 §4）。
- 同样**没有**卷类型断言（`fsutil fsinfo volumeinfo` / `Get-Volume.FileSystemType`）。

#### 3.4.3 验证层（核心证据）

`024/tests/run_tests.ps1` 共 39 行，5 个用例。ADS 判定的三把武器全部用上：

**用例 `real_stream_utf8`（`:9`）——一条断言里同时验 ADS 存在性、往返值、流枚举、UTF-8 无 BOM 字节**：

```powershell
$p=Join-Path $fixture '文档 [1].txt';[IO.File]::WriteAllText($p,'main');
$r=& $candidate -Path $p -Stream meta -Action Set -Value '秘密';
$g=& $candidate -Path $p -Stream meta -Action Get;
$streams=Get-Item -LiteralPath $p -Stream *;
($r.Status-eq 'set')-and($g.Status-eq 'found')-and($g.Value-eq '秘密')-and
(@($streams|Where-Object Stream -eq 'meta').Count-eq 1)-and
([Convert]::ToHexString([IO.File]::ReadAllBytes($p+':meta'))-eq 'E7A798E5AF86')
```
（`024/tests/run_tests.ps1:9`，摘录整理）

四个层次的独立验证：

1. `$r.Status -eq 'set'`、`$g.Value -eq '秘密'`：候选的 API 契约（必要但不充分——候选可以只用内存字典糊弄过去）。
2. **`Get-Item -LiteralPath $p -Stream *`**：这是**独立于候选的磁盘枚举**，直接从文件系统列出该文件的所有数据流，并断言名为 `meta` 的流**恰好出现 1 次**。这条把"候选自己编造返回值"的实现排除掉——流必须真的存在于 NTFS 上。注意夹具文件名 `文档 [1].txt` 又带**中文 + 空格 + 方括号**，且这里用 `-LiteralPath`（不用通配符解释）。
3. **`[IO.File]::ReadAllBytes($p+':meta')`**：用 **`路径:流名` 的 ADS 语法直接读原始字节**。这是最底层的证据——绕开候选、绕开 PowerShell 的 `-Stream`，直接按 NTFS 的 ADS 寻址方式读。
4. **`[Convert]::ToHexString(...) -eq 'E7A798E5AF86'`**：'秘密' 的 UTF-8 编码 = `秘`(U+79D8)→`E7 A7 98`、`密`(U+5BC6)→`E5 AF 86`。**注意十六进制串以 `E7` 开头，没有 `EF BB BF`**——这就把「UTF-8 无 BOM」验到了字节级。若候选写了 BOM，字节会变成 `EFBBBFE7A798E5AF86` → FAIL；若候选用了 UTF-16 或 GBK → FAIL。**用十六进制而不是字符串比较，正是为了把 BOM 与编码问题暴露出来**（字符串比较会把 BOM 当不可见字符而"通过"）。

**用例 `replace_empty`（`:15`）——空流必须真实存在且 0 字节**：

```powershell
& $candidate -Path $p -Stream data -Action Set -Value 'long text'|Out-Null;
& $candidate -Path $p -Stream data -Action Set -Value ''|Out-Null;
$g=& $candidate -Path $p -Stream data -Action Get;
($g.Status-eq 'found')-and($g.Value-eq '')-and([IO.File]::ReadAllBytes($p+':data').Length-eq 0)
```

- 先写 `'long text'` 再写 `''`：断言 `Status='found'`（**流还在**）、`Value=''`，且 `$p+':data'` 的字节长度为 **0**。
- 这条排除了「Set 空值 = 删除流」的近似实现（那种实现会让 `ReadAllBytes` 抛异常或 Get 返回 missing）。它精确区分了 **"存在的空流"** 与 **"不存在的流"**——这是 ADS 语义里的真实区别。

**用例 `remove_existing`（`:21`）——流必须真的消失**：

```powershell
[IO.File]::WriteAllText($p+':data','old');           # 夹具用 ADS 语法直接预置流
$r=& $candidate -Path $p -Stream data -Action Remove;
$g=& $candidate -Path $p -Stream data -Action Get;
$streams=Get-Item -LiteralPath $p -Stream *;
($r.Status-eq 'removed')-and($g.Status-eq 'missing')-and(@($streams|Where-Object Stream -eq 'data').Count-eq 0)
```

- 夹具用 `[IO.File]::WriteAllText($p+':data','old')` **预置真实流**（注意用 .NET API 而非 PowerShell cmdlet，够底层）。
- Remove 后再次 `Get-Item -Stream *` 枚举，断言名为 `data` 的流**计数为 0**——不是相信候选说删了，而是去磁盘上数。

**用例 `main_other_preserved`（`:27`，P2P）——不污染主文件与无关流**：

```powershell
[IO.File]::WriteAllText($p,'main');
[IO.File]::WriteAllText($p+':other','safe');
& $candidate -Path $p -Stream target -Action Set -Value x|Out-Null;
& $candidate -Path $p -Stream target -Action Remove|Out-Null;
([IO.File]::ReadAllText($p)-eq 'main')-and([IO.File]::ReadAllText($p+':other')-eq 'safe')
```

- 主文件内容与无关流 `other` 都必须逐字不变——直接落地题面「主文件内容、其他数据流和文件名必须保持不变」。

**用例 `missing_idempotent`（`:33`，P2P）**：对不存在的流连续两次 Remove 都返回 `'missing'`，Get 返回 `'missing'`，主文件未变 → 幂等。

**判定封装**（`:37-39`）：与 031 完全同构（同一份 `aggregate_results.ps1`），`Infrastructure:` → `INVALID`、全 PASS → 1。

#### 3.4.4 夹具清理

- 测试内部（`024/tests/run_tests.ps1:3`）：与 031 逐字节相同的 `Clear-Fixtures`——**先 `SetAttributes(..., Normal)` 复位属性位，再 `Remove-Item -Recurse -Force`**，`Test-Path` 守卫保证幂等。
- ADS 本身的清理无需特殊处理：**ADS 是随主文件一起删除的**（NTFS 上不存在"孤儿流"），所以删掉文件即清理干净。这是 ADS 相比 junction/硬链接更省心的清理特性。
- 环境层（`024/environment/cleanup.ps1`）= 031 同款：**卷根拒绝**（`if($full-eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}`）+ 属性位复位 + 递归删除 + `Test-Path` 幂等。
- 同样有 `$reg` 注册表模板残留（`:7`/`:10` 等）。

---

### 3.5 `037` windows-hardlink-isolation-002 —— NTFS 硬链接写入隔离

**机制关键词**：`New-Item -ItemType HardLink`、硬链接共享数据的隔离（读-改-写 vs 替换）、UTF-8 无 BOM、方括号字面路径、替换后必须仍是普通文件（`ReparsePoint` 位为 0）。

#### 3.5.1 题面层

> **原文（instruction.md:1）**：「我们有个更新小工具，同一份文件有时会被 **NTFS 硬链接**引用。请修好 workspace/candidate.ps1，参数是 -Path 和 -Text。把指定路径的内容更新为 Text 的 UTF-8（不带 BOM）字节，但**其他硬链接必须保留原来的内容**；指定路径本身仍是一个**普通文件**。文件名可能有空格、中文或方括号，不能按通配符解释。不存在的路径应创建文件。不要动同目录的其他文件，返回对象应包含 Status="updated"。只需要支持当前用户可写的 NTFS 本地目录，不处理目录或重解析点。」
>
> — 中文解释：这是一道**语义反转**的题。表面对应"写文件"，但加了硬链接条件后，"正常写法"就变成错误的：
> - 「同一份文件有时会被 NTFS 硬链接引用」+「**其他硬链接必须保留原来的内容**」：在 NTFS 上，同一份数据（同一个 MFT 记录/Data Attribute）可以有多个文件名（硬链接）。若直接 `WriteAllText`（打开→截断→写），**所有硬链接都会看到新内容**——因为它们是同一份数据。要满足「其他硬链接保留原内容」，必须**先断开共享**：把新内容写到临时文件，然后**替换**目标路径（`File.Replace` / `MoveFileEx` / 删除+改名），使目标路径指向新的数据，而旧的硬链接仍指向旧数据。这条要求把"写文件"逼成了"替换文件"。**这是在 POSIX 上不成立的题面**：Linux 没有 `New-Item -ItemType HardLink`，题面也直接引用了 NTFS 硬链接这一 Windows/NTFS 数据模型概念。
> - 「指定路径本身仍是一个**普通文件**」：直接堵住"用符号链接/重解析点顶替"的偷懒实现（若用 symlink 指向临时文件，属性位会变）。验证层对此有专门断言（见 3.5.3）。
> - 「不处理目录或重解析点」：显式收窄范围，避免与 007/017 的边界问题叠加。
>
> **原文（instruction.md:3）**：「运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。」

**是否显式点名具体 NTFS 机制**：是（NTFS 硬链接 + 普通文件 + UTF-8 无 BOM）。
**是否声明「不需要其他操作系统版本」**：无显式措辞。

#### 3.5.2 环境层

`037` 的 `environment/` 下 **7 个文件与 `017` 逐字节相同**（SHA256 全部 SAME）。所以：

- `validate_environment.ps1:1-5` 同 017：`$IsWindows` + `PSVersion -lt [version]'7.5'` + `Win32_OperatingSystem.Version -ne '10.0.20348'` → **非 Windows 必然失败**。
- `task.toml:19-27` 同 017（`filesystem="NTFS"` 等）。
- `prepare.ps1` 同 017（新目录保护 + 复制 candidate，**未调用 validate**）。
- **没有** NTFS 卷断言，**没有**硬链接能力探测（例如实际创建一个硬链接试一下）。后者尤其值得补：硬链接只在 NTFS 上可用，若工作区落在 ReFS/FAT32 上，`New-Item -ItemType HardLink` 夹具会失败 → 在本模板下会退化成候选 FAIL（`$detail` 不以 `Infrastructure:` 开头，因为夹具创建语句在 try 块内且未抛 `Infrastructure:` 前缀异常，见 3.5.3 的弱项）。

#### 3.5.3 验证层（核心证据）

`037/tests/run_tests.ps1` 共 42 行，5 个用例。

**用例 `hardlink_split`（`:11`）——本题的机制核心，用"内容隔离性"证明硬链接被断开**：

```powershell
$p=Join-Path $fixture 'a.txt';$other=Join-Path $fixture 'linked.txt';
[IO.File]::WriteAllText($p,'before');
New-Item -ItemType HardLink -Path $other -Target $p|Out-Null;
& $candidate -Path $p -Text 'after'|Out-Null;
([IO.File]::ReadAllText($p)-eq 'after')-and([IO.File]::ReadAllText($other)-eq 'before')
```
（`037/tests/run_tests.ps1:11`，摘录整理）

- 夹具：`[IO.File]::WriteAllText($p,'before')` 建文件，再用 **`New-Item -ItemType HardLink -Path $other -Target $p`** 建第二个名字 `linked.txt` —— **同一个 NTFS 数据对象的两个目录项**（`New-Item -ItemType HardLink` 是 Windows PowerShell 7 的 cmdlet，Linux 上不存在此 `-ItemType`）。
- 断言：写入后 `$p` 的内容是 `'after'`，而 **`$other` 必须还是 `'before'`**。
- **这就是"是否真的做了隔离"的判定**：直接 `WriteAllText($p, 'after')` 会改同一份数据 → `$other` 变成 `'after'` → FAIL。只有实现「写临时文件 + 原子替换目标路径」才能让两个名字分道扬镳。验证层不需要 FileID、不需要 `GetFileInformationByHandle`——**内容隔离性本身就是硬链接共享关系的观测面**。

**用例 `split_again`（`:35`）——替换后再次写入仍需隔离 + 返回形状**：

```powershell
$p=Join-Path $fixture '[源] file.txt';$seed=Join-Path $fixture 'seed.txt';$other=Join-Path $fixture '引用.txt';
[IO.File]::WriteAllText($seed,'original');
New-Item -ItemType HardLink -Path $other -Target $seed|Out-Null;
[IO.File]::Move($seed,$p);
$r=& $candidate -Path $p -Text '新';
$q=& $candidate -Path $p -Text '再次';
(@($r).Count-eq 1)-and($r.Status-eq 'updated')-and($q.Status-eq 'updated')-and
([IO.File]::ReadAllText($p)-eq '再次')-and([IO.File]::ReadAllText($other)-eq 'original')
```
（`037/tests/run_tests.ps1:35`，摘录整理）

- 夹具更有层次：先建硬链接 `引用.txt` ← `seed.txt`，再 `[IO.File]::Move($seed,$p)` 把其中一个名字**改名**为 `[源] file.txt`（含方括号、空格、中文）。改名后两个名字仍共享同一份 `'original'` 数据。
- 然后**连续两次**调用（`'新'` → `'再次'`），断言：`$p` 是 `'再次'`、`$other` 仍是 `'original'`。
- **两次调用的设计用意**：第一次替换已把 `$p` 与旧数据断开（此时 `$p` 是独立数据、`$other` 指向旧数据）；第二次是在**已隔离的普通文件**上写入。这排除了"只在第一次特殊处理"或"替换后留下奇怪的半隔离状态"的实现。
- `(@($r).Count-eq 1)`：**返回值必须是单个对象而不是数组**。这条防的是实现里用 `Write-Output` 顺带输出了额外内容，导致捕获到数组——与题面「不输出额外日志」呼应。

**用例 `literal_utf8_create`（`:17`）——UTF-8 无 BOM + 方括号字面路径 + 创建语义**：

```powershell
$p=Join-Path $fixture '中文 [1].txt';
& $candidate -Path $p -Text '更新'|Out-Null;
[IO.File]::Exists($p)-and([Convert]::ToHexString([IO.File]::ReadAllBytes($p))-eq 'E69BB4E696B0')
```

- 文件**不存在**时调用（覆盖「不存在的路径应创建文件」）。文件名 `中文 [1].txt` 含中文 + 空格 + 方括号（方括号是通配符元字符 → 验"不能按通配符解释"）。
- `[Convert]::ToHexString` 逐字节比对：'更新' = `更`(U+66F4)→`E6 9B B4`、`新`(U+65B0)→`E6 96 B0` → `E69BB4E696B0`。**串首是 `E6` 而非 `EF BB BF`** → 无 BOM。手法与 024 完全一致（同一个作者习惯）。

**用例 `return_and_plain`（`:29`）——"替换后仍是普通文件"的核心证明**：

```powershell
$p=Join-Path $fixture 'plain.txt';[IO.File]::WriteAllText($p,'old');
$r=& $candidate -Path $p -Text '';
$item=Get-Item -LiteralPath $p;
($r.Status-eq 'updated')-and($item.PSIsContainer-eq $false)-and
(($item.Attributes-band [IO.FileAttributes]::ReparsePoint)-eq 0)-and
([IO.File]::ReadAllBytes($p).Length-eq 0)
```

- 用 `Get-Item -LiteralPath $p` 取**目录项元数据**，断言三件事：
  1. `$item.PSIsContainer -eq $false`：**不是目录**（防"用目录顶替"）。
  2. **`($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0`**：**重解析点属性位必须为 0**。这是本题**唯一的属性位断言**，作用是：如果候选为了让 `$p` 指向新数据而用了符号链接/junction（一种很自然的偷懒实现），`ReparsePoint` 位（1024）就会被点亮 → FAIL。**这正好是任务书里「替换后 FileID」意图的实现方式——但用的是属性位而非 FileID。**
  3. `[IO.File]::ReadAllBytes($p).Length -eq 0`：写空文本后文件必须是 0 字节。

**用例 `neighbor_preserved`（`:23`，P2P）**：同目录 `neighbor.txt` 内容不变。

**判定封装**（`:39-42`，`:38` 为 `finally` 清理）：与 017 同构（同一份 `aggregate_results.ps1`）。

**弱项（如实记录，两条）**：

1. **没有 FileID 判定**。题名 `hardlink-isolation` 与任务书提到的"替换后 FileID"在这份 `run_tests.ps1` 里**没有任何对应断言**（没有 `GetFileInformationByHandle`、没有 `nFileIndex`、没有 `fsutil hardlink`）。它靠**内容隔离 + ReparsePoint 位**来判定。这两条已经能排除主要错误实现，但强度低于 §4 里 002.2 那种「用 `VolumeSerialNumber:FileIndex:NumberOfLinks` 直接验证链接数与同一性」的写法。
2. **夹具失败会退化成候选 FAIL**。`:11` 里 `New-Item -ItemType HardLink` 与 `[IO.File]::WriteAllText` 都直接写在 try 块内，且抛出的异常**不带 `Infrastructure:` 前缀**，所以 `catch` 里 `if($detail.StartsWith('Infrastructure:')){$status='ERROR'}` 不会命中 → 记为 `FAIL`。若在非 NTFS 卷上跑（硬链接创建失败），会把基础设施问题误判为候选失败。对比 031/024 在夹具创建处显式抛 `Infrastructure:` 前缀（`031/tests/run_tests.ps1:4` `throw ('Infrastructure: fixture creation failed: '+...)`）——**031/024 的做法更正确，应当统一**。

#### 3.5.4 夹具清理

- 测试内部（`037/tests/run_tests.ps1:38`）：`finally { if(Test-Path -LiteralPath $fixtureRoot){Remove-Item -LiteralPath $fixtureRoot -Recurse -Force} }`——`Test-Path` 守卫 + `finally` 保证幂等。
- **硬链接清理无需特殊处理**：删除其中一个名字即减少链接计数，删除全部名字后数据才释放（`Remove-Item -Recurse` 会把两个名字都删掉）。所以硬链接比 junction 好清理——**没有"穿透删除目标"的风险**。
- 环境层（`037/environment/cleanup.ps1`）= 017 同款：**卷根拒绝** + `Test-Path` 守卫 + `Remove-Item -LiteralPath $full -Force -Recurse`。同样**没有属性位复位**（弱项，与 017 同）。

---

## 4. 延伸对照：同批更高强度档位的写法（样本外，供上探参考）

下面的证据来自同一 `extracted/` 目录，但**不属于我负责的 5 个样本**，仅作为「比本批 5 题更强」的写法参照，帮助判断还有哪些 Windows 机制可注入我方三题。

| 强度维度 | 本批 5 题所用 | 同批其他题的更强写法（文件:行） |
|---|---|---|
| 文件同一性 / 硬链接数 | 内容隔离性 + `ReparsePoint` 位（037） | P/Invoke `CreateFileW`+`GetFileInformationByHandle`，返回 `VolumeSerialNumber:FileIndex:NumberOfLinks` 三元组作身份指纹（`002.2/tests/test_fail_to_pass.ps1:50-56,81`） |
| 硬链接夹具 | `New-Item -ItemType HardLink`（037） | `fsutil.exe hardlink create`（`002.2/environment/provision.ps1:23`、`010/tests/test.ps1:7`） |
| ADS 枚举 | `Get-Item -Stream *` + `路径:流名`（024） | P/Invoke `FindFirstStreamW`/`FindNextStreamW`，并注释说明「`-Stream` 会把 `:$DATA` 类型后缀吃掉，所以一律走原始形式」（`002.2/tests/test_fail_to_pass.ps1:50-53,113-119`） |
| 稀疏文件 | 未涉及 | `fsutil.exe sparse setflag`（`002.2/environment/provision.ps1:17`） |
| 卷/压缩细节 | 未涉及 | `GetCompressedFileSizeW`（`002.2/tests/test_fail_to_pass.ps1:53`） |
| 真实安全描述符 | 未涉及（仅 007 用 icacls 做账号隔离） | `Get-Acl` 读 SDDL 并逐项比对 owner/ACE/继承标志（`002.3/tests/test_fail_to_pass.ps1:13-31,88-182`）；P/Invoke `RegGetKeySecurity`/`RegSetKeySecurity` 做注册表 DACL 指纹（`036/tests/RegistryAclGuard.cs:9-16`） |
| ADS 能力探测（环境自证） | 本批 5 题**都没有** | validate 里试写 `Zone.Identifier` 并读回验证（`002.6/environment/validate_environment.ps1:17-18`）+ `docker-smoke.ps1:18-35` 建镜像时冒烟 |
| 特权（SeBackup 等） | 未涉及 | P/Invoke `OpenProcessToken`+`LookupPrivilegeValue`+`AdjustTokenPrivileges`（`002.2/environment/apply_case_security.ps1:37-40`） |
| 重解析点防护（清理时） | 017/037 未做；031/024 未做 | cleanup 里先判 `ReparsePoint` 位再删，并拒绝 reparse 根（`002.2/environment/cleanup.ps1:11,23`、`002.3/environment/cleanup.ps1:10,23`） |
| `Zone.Identifier` 来源标记 | 未涉及 | 整题围绕 `Zone.Identifier` 流的精确移除与幂等（`002.6/instruction.md:5,15,28`） |

结论性提示：**本批 5 题是"对象层"绑定（真实 NTFS 对象 + 位掩码/字节级判定），上面这些是"内核结构层"绑定（FileID、reparse tag、SDDL、特权、稀疏/压缩属性）。** 我方三题若要一次性摆脱"平台无关"判定，做到本批 5 题这一档已足够；若要冲"Windows 价值极高"，需要补一个记录级身份断言（FileID 三元组）与一个安全描述符断言。

---

## 5. 可复用检查清单：为一道题注入 NTFS/文件系统类 Windows 机制依赖

### 5.1 题面必写项（instruction.md）

- [ ] **开篇就点名 NTFS 对象类型**，不要只描述行为。写「NTFS 备用数据流」「NTFS 硬链接」「重解析点（例如 junction）」「Windows 文件属性位」这类名词（本批 5 题全部做到了）。
- [ ] **写出负面约束**，堵住近似实现。例：「主文件内容、其他数据流和文件名必须保持不变，不得把数据流内容写进主文件」（024:1）、「指定路径本身仍是一个普通文件」（037:1）、「拒绝时不能创建或改动目标中的任何文件」（007:5）。
- [ ] **写出判定所依赖的语义边界**，而不是结果。例：「所有重解析点都必须跳过，**包括指向根目录内部的链接**」（017:1）——把"防逃逸"升级为"查属性本身"；「只修改 Hidden 和 ReadOnly，**必须保留 Archive、System 以及其他属性**」（031:1）——把"设属性"升级为"位运算"。
- [ ] **点名机制的具体约束**。例：「Stream 是非空、**不含冒号和目录分隔符**的自定义流名称」（024:3，ADS 语法约束）；「**同一个 NTFS 卷上**」（007:5）；「扩展名不区分大小写，路径使用反斜杠，按 OrdinalIgnoreCase 排序」（017:1）。
- [ ] **声明唯一目标环境**：「真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS」（031:5 / 024:5 / 017:3 / 037:3 逐字同构）。
- [ ] **补一句本批 5 题都没写的话**（建议新增）：「本题只需在 Windows Server 2022 x64 build 20348 + NTFS 上成立；不需要、也不应支持 Linux/macOS 或其他 Windows 版本，也不得用 xattr/模拟层替代 NTFS 语义。」——把"Windows 专属"从暗示变成显式要求，直接回应质检的"平台无关"质疑。
- [ ] **给出精确的返回契约与编码契约**（§3.4.3 证明这是可验证的）：`Status="updated"` / `{"status":"ok"}` + 退出码 0/2/3 / UTF-8 **无 BOM**。
- [ ] **约束改动面与副作用**：「只修改 <candidate 路径>，保持参数入口；离线运行，不输出额外日志」（5 题统一句式）。

### 5.2 环境必做项（environment/）

- [ ] **基线镜像用 Windows 容器**：`mcr.microsoft.com/powershell:7.5-windowsservercore-ltsc2022`（031/017/024/037:task.toml:2）或 `mcr.microsoft.com/dotnet/framework/runtime:4.8-windowsservercore-ltsc2019@sha256:...`（007，digest 固定更好）。
- [ ] **`validate_environment.ps1` 三重硬失败**（缺一即可在别的 OS 上"通过"）：
  - `if(!$IsWindows){throw ...}`
  - PowerShell 版本：精确 `-ne '7.5.10'`（031 更严）或下限 `-lt [version]'7.5'`（017/037）；
  - OS build：`(Get-CimInstance Win32_OperatingSystem).Version -ne '10.0.20348'`（只有 Windows 有 CIM 提供程序）。
- [ ] **`prepare.ps1` 首行调用 `validate_environment.ps1`**（照抄 `031/environment/prepare.ps1:4`；017/037 漏了这一步，是缺陷）。
- [ ] **`prepare.ps1` 加新目录保护**：`if(Test-Path -LiteralPath $WorkspaceRoot){throw 'WorkspaceRoot must be a new directory'}`（幂等 + 防覆盖）。
- [ ] **`task.toml` 写结构化环境声明**：`os="windows"` / `build="10.0.20348"` / `shell="PowerShell 7.5.10"` / **`filesystem="NTFS"`** / `network_mode="no-network"` / `permissions="current user, no elevation needed"`。
- [ ] **`task.toml` 加机制标签**（照抄 007 的做法，本批其他 4 题都没有）：`category="windows-filesystem"`、`tags=["windows","ntfs","reparse-point","junction",...]`。这让题在索引层就被识别为 Windows 机制题。
- [ ] **`adapter.toml` 声明 `adapter="native-windows"` + `network_mode="offline"`**；`Dockerfile` 用 Windows `FROM`，路径用 `C:/`（031/017/024/037 一致）。
- [ ] **（本批 5 题的共同缺口，建议补）运行时断言卷类型真的是 NTFS**：`(Get-Volume -DriveLetter ($WorkspaceRoot[0])).FileSystemType -eq 'NTFS'` 或 `fsutil fsinfo volumeinfo`；失败即 throw。`filesystem="NTFS"` 目前只是声明，没有校验。
- [ ] **（缺口，建议补）机制能力探测**：像 `002.6/environment/validate_environment.ps1:17-18` 那样，在 validate 里真的试一次目标机制（写一个 ADS 流并读回 / 建一个 junction 并删除 / 建一个硬链接并检查链接数），失败即 `throw`。这能保证「夹具造不出来"在环境阶段就暴露，而不是变成候选 FAIL。
- [ ] **如需权限模型**：`net user <AgentUser> /add` + `icacls <root> /grant '<AgentUser>:(OI)(CI)RX'`，每个 `icacls` 后 `if ($LASTEXITCODE -ne 0) { throw ... }`（照抄 `007/environment/Dockerfile:8-20`）；`task.toml` 里 `[agent] user` / `[verifier] user` 分开。
- [ ] **编译型题把编译器路径写死并断言存在**：`$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe` + `if (-not (Test-Path $csc)) { throw 'Required .NET Framework x64 C# compiler missing' }`（`007/environment/build.ps1:6-7`）。

### 5.3 验证必做项（tests/run_tests.ps1）

- [ ] **夹具一律运行时动态构造**，根目录用 UUID：`Join-Path $WorkspaceRoot ('fixtures-'+[Guid]::NewGuid().ToString('N'))`（5 题统一）。不要依赖 `environment/workspace/` 里预置的夹具（本批 5 题的 `environment/workspace/` 根本不存在）。
- [ ] **夹具必须是真的 NTFS 对象**，用下面这些调用（本批实测可用）：
  - junction：`cmd.exe /c mklink /J $link $target`（007:12）或 `New-Item -ItemType Junction -Path $link -Target $target`（017:17，更可读且天然 Windows-only）；
  - 符号链接：`New-Item -ItemType SymbolicLink`（目录 + 文件各来一个，017:41）；
  - 硬链接：`New-Item -ItemType HardLink -Path $new -Target $existing`（037:11）或 `fsutil hardlink create`；
  - ADS：`[IO.File]::WriteAllText($p+':stream','...')` 或 `Set-Content -LiteralPath $p -Stream name -Value ...`；
  - 属性位：`[IO.File]::SetAttributes($p, [IO.FileAttributes]39)`（031:15）；
  - 循环链接：`New-Item -ItemType Junction -Path $root\loop -Target $root`（017:17，自指）。
- [ ] **判定读磁盘，不读候选返回值**。四条独立读取路径按需选：
  - `[IO.File]::GetAttributes($p)` 读位，用 `-band <掩码>` 断言（031:9/15/21/27）；
  - `Get-Item -LiteralPath $p -Force` 读 `.Attributes` / `.PSIsContainer`（031:27、037:29）；
  - `Get-Item -LiteralPath $p -Stream *` 独立枚举真实流并计数（024:9/21/27）；
  - `[IO.File]::ReadAllBytes($p+':stream')` / `[Convert]::ToHexString(...)` 读**字节**并比对十六进制串——**验编码/BOM 必须用字节，不能用字符串比较**（024:9 `'E7A798E5AF86'`、037:17 `'E69BB4E696B0'`）。
- [ ] **设计"让错误实现必然翻车"的对抗性夹具**（本批最精彩的部分）：
  - 文件名同时含**中文 + 空格 + 方括号**（`文件 [1].txt`、`文档 [1].txt`、`中文 [1].txt`、`[源] file.txt`）→ 打死通配符/字符串拼接实现；
  - **文件符号链接起一个符合扩展名过滤条件的名字**（017:41 的 `filelink.log`）→ 打死"只按扩展名收集"的跨平台实现；
  - **junction 指向根目录内部**（017:29 的 `alias` → `root\inner`）→ 打死"只防逃逸"的实现；
  - **junction 指向外部且目标里有诱饵文件**（007:18 `outside`、017:17 `secret.log`）→ 打死"跟随链接"的实现；
  - 目标目录**本身是 junction** 且断言"没写穿"（007:19 `-not (Test-Path ...\outside\new.txt)`）；
  - 属性夹具**预置 System|Archive**（031:15 的 `39`）→ 打死"整组覆盖属性"的实现；
  - 硬链接**改名后再连续写两次**（037:35）→ 打死"只处理第一次"的实现；
  - **空值 vs 不存在**（024:15 空流必须 0 字节且 `Status='found'`）；
  - **空结果必须是非 null 空数组**（017:35）；
  - **返回值必须是单对象**（037:35 `@($r).Count -eq 1`），防候选输出噪音。
- [ ] **基础设施失败与候选失败严格分离**（031:4/9、024:4/9、017、037 的模式）：

```powershell
try{ New-Item -ItemType Directory -Path $fixtureRoot|Out-Null }catch{ throw ('Infrastructure: fixture creation failed: '+$_.Exception.Message) }
...
catch {$detail=$_.Exception.Message;if($detail.StartsWith('Infrastructure:')){$status='ERROR'}}
```

  `ERROR` → `validity='INVALID'` / `score=$null` / `exit 2`。**（注意 037 的硬链接/属性夹具处漏了这个前缀约定，应统一到 031 的做法。）**
- [ ] **严格校验脚本块返回值**：`$passed=& { ... }; if(@($passed).Count-eq 1-and $passed-eq $true){...}`（031:9）——避免候选的额外输出被当成通过信号。
- [ ] **多份元数据互相印证 + 二次校验**：`run_tests.ps1` 内嵌 `$required` 列表，`rubric.json` / `required_testcases.json` / `testcase_mapping.csv` 同源，`aggregate_results.ps1` 再校验用例数量、id 唯一性、状态取值（007:7-9）；`judge.toml` 带 `rubric_sha256` 防篡改。
- [ ] **binary 评分**：全部 required PASS → 1，任一 FAIL → 0，基础设施 → INVALID/null（`rubric.json` 的 `rule` 字段显式写出）。
- [ ] **黑盒调用（编译型题优先）**：把候选当进程调，读**真实退出码 + stdout**（007:11 `Invoke-App`），题面就把退出码协议写死（007:7 的 0/2/3）。

### 5.4 夹具清理必做项

- [ ] **`Test-Path` 守卫 + `finally` = 幂等**（5 题统一模式）：`finally { if(Test-Path -LiteralPath $fixtureRoot){ Remove-Item -LiteralPath $fixtureRoot -Recurse -Force } }`。
- [ ] **清属性位夹具前先复位**（031:3、024:3 的 `Clear-Fixtures`）：`Get-ChildItem -Recurse -File -Force | ForEach-Object { [IO.File]::SetAttributes($_.FullName,[IO.FileAttributes]::Normal) }` **再** `Remove-Item -Recurse -Force`。不加 `-Force` 连 Hidden 文件都枚举不到；不复位 ReadOnly 会删不掉。
- [ ] **删 junction/symlink 只删链接本身**，用 `cmd /c rmdir $link`（007:13）或 `Remove-Item -LiteralPath $link -Force`（**不加 `-Recurse`**）。**绝不**对含链接的目录直接 `Remove-Item -Recurse`（见 5.5）。
- [ ] **环境层 cleanup 拒绝卷根**（031/024/017/037 统一）：`$full=[IO.Path]::GetFullPath($WorkspaceRoot); if($full -eq [IO.Path]::GetPathRoot($full)){throw 'Refusing volume root'}`。
- [ ] **环境层 cleanup 的路径前缀要覆盖测试夹具根**（007 做对了）：`cleanup.ps1` 的 `C:\bench-fixtures` 必须包含 `test.ps1` 用的 `C:\bench-fixtures\reparse`。
- [ ] **cleanup 加 `-ErrorAction SilentlyContinue`（或整体 `$ErrorActionPreference='SilentlyContinue'`）+ `Test-Path` 守卫**（007:2-3），保证「本来就没有夹具」时也成功退出。
- [ ] **`restore.ps1` = cleanup + prepare**（031:2、017:2-3），让"重跑"安全。
- [ ] **ADS 与硬链接的清理是免费的**（ADS 随主文件删、硬链接删名字即减计数）；**junction/symlink 必须显式处理**——这是唯一真正需要额外小心的一类。

### 5.5 常见坑（本批样本实际踩到或差点踩到的）

1. **`Remove-Item -Recurse` 处理 junction 会穿透删目标**。这是 PowerShell 5.1 与 6+ 的著名行为差异。本批的真实风险点：
   - `007` 的 `test.bat:2` 用的是 **`powershell.exe`（5.1）**，而 031/017/024/037 的 `test.bat:3` 用的是 **`pwsh.exe`（7.x）**。007 的 `Reset`（`test.ps1:10`）对 `$root` 做 `Remove-Item -Recurse -Force`，而 `$root` 里放着指向 `$fixture\outside` 的 junction —— **这正是 007 为什么要额外写 `Remove-Junction` 并在 `destination_junction_rejected` 用例末尾立即调用（`:19`）**。做同类题时：要么统一用 `pwsh`，要么先用 `rmdir` 清掉所有链接再递归删。
   - `017`/`037` 的 `cleanup.ps1:3` 直接 `Remove-Item -LiteralPath $full -Force -Recurse`，而 017 的夹具里就有 junction 与 symlink，**没有先删链接**。虽然其 `run_tests.ps1` 的 `finally`（`:44`/`:38`）已先删掉了 `$fixtureRoot`，理论上链接不会活到环境清理阶段，但**一旦某用例中途崩溃**（`finally` 前进程被杀），残留链接就会进入 cleanup 路径。建议把 `002.2/environment/cleanup.ps1:11` 的写法并入：先判 `ReparsePoint` 位，再决定删链接还是删目录。

2. **属性位夹具不清干净会残留**。ReadOnly 文件在部分删除路径上会失败；Hidden 文件不加 `-Force` 枚举不到。`031`/`024` 的 `Clear-Fixtures` 处理了，`017`/`037`/`007` 的 cleanup **没有**复位属性位。

3. **`Get-Item` 读 Hidden 文件必须加 `-Force`**（031:27 用了 `-Force`）。忘了会取不到对象，断言以奇怪的方式失败。

4. **编码/BOM 判定绝不能用字符串比较**。`[IO.File]::ReadAllText()` 会把 BOM 当不可见字符吞掉，"看起来"通过。必须 `[IO.File]::ReadAllBytes()` + `[Convert]::ToHexString()`（024:9、037:17）。

5. **路径一律用 `-LiteralPath`**。题面写了"按字面处理/不能按通配符解释"，验证层的每个 `Get-Item`/`Set-Content`/`WriteAllText` 都要跟上；夹具名里放方括号，让漏用 `-LiteralPath` 的实现暴露。

6. **夹具创建失败必须带 `Infrastructure:` 前缀**，否则会被记成候选 FAIL（037 的硬链接夹具漏了；031:4 是正确写法）。

7. **`filesystem="NTFS"` 只是声明**。本批 5 题没有一个在运行时校验卷类型。加上 `Get-Volume`/`fsutil fsinfo volumeinfo` 断言，才能防止题在 ReFS/FAT32 上跑出不同的通过结果。

8. **`prepare.ps1` 不调 `validate_environment.ps1`**（017/037 漏了）→ 前置条件不成立时不会在准备阶段失败，而是拖到测试阶段变成假 FAIL。

9. **版本比较用 `[version]` 类型**（017:3/037:3 `-lt [version]'7.5'`），别用字符串比较（`'7.10' -lt '7.5'` 为真，是错的）。

10. **符号链接创建需要权限**（开发者模式 / `SeCreateSymbolicLinkPrivilege`）。017:41 用 `New-Item -ItemType SymbolicLink`，而 `task.toml:27` 写的是 `permissions="current user, no elevation needed"` —— 二者存在张力。**出题时必须在目标容器里实测符号链接能建成**，否则该用例会稳定失败。

11. **不要复制模板残留**。031/017/024/037 的 `run_tests.ps1` 里都有一对**与本题无关**的注册表清理代码（`$reg='Software\OutsideHarborBench\'+GUID` 定义后从未写入，只在 `finally` 里 `DeleteSubKeyTree($reg,$false)`）；031:25 还写成双反斜杠 `'Software\\OutsideHarborBench\\'` 与其他用例不一致。它无害（`throwOnMissingSubKey=$false`），但会让读者误以为题目涉及注册表——**从这批题复制骨架时应当删掉**。

---

## 6. 附：五题机制关键词矩阵

| 维度 | 031 文件属性 | 007 重解析点复制 | 017 junction 边界 | 024 ADS | 037 硬链接隔离 |
|---|---|---|---|---|---|
| 题面点名的 Windows 机制 | Hidden/ReadOnly/Archive/System 属性位、字面路径 | 重解析点（junction）、同一 NTFS 卷、退出码协议 | junction、目录符号链接、循环链接、重解析点、反斜杠、OrdinalIgnoreCase | **NTFS 备用数据流**、流名不含冒号/分隔符、UTF-8 无 BOM | **NTFS 硬链接**、普通文件、UTF-8 无 BOM |
| 题面环境声明 | ✅ :5 | ❌（仅 task.toml） | ✅ :3 | ✅ :5 | ✅ :3 |
| 「不需要其他 OS」显式声明 | ❌ | ❌ | ❌ | ❌ | ❌ |
| `task.toml` 机制标签 `tags` | ❌ | ✅ `ntfs/reparse-point/junction` | ❌ | ❌ | ❌ |
| validate 是否 `$IsWindows` + build | ✅ 精确 7.5.10 | ❌ 仅查文件存在 | ✅ ≥7.5 + 20348 | ✅ 同 031 | ✅ 同 017 |
| prepare 是否调 validate | ✅ | ❌ | ❌ | ✅ (同 031) | ❌ |
| 卷类型 NTFS 运行时断言 | ❌ | ❌ | ❌ | ❌ | ❌ |
| 真实夹具 | `SetAttributes(p,39)` + `文件 [1].txt` | `mklink /J` 源侧/目标侧 | `New-Item Junction`（外部+循环+内部）、`SymbolicLink`（目录+文件） | `$p+':meta'` 写入、`-Stream *` 枚举 | `New-Item HardLink` + `[IO.File]::Move` 改名 |
| 判定依据 | `GetAttributes` + `-band 3/36` 位掩码 | 进程退出码 2 + 目标零副作用 | `Files` 整串相等（跳过性+排序+大小写） | `-Stream *` 计数 + `ReadAllBytes` 十六进制 | 内容隔离性 + `ReparsePoint` 位 |
| 是否用 P/Invoke / fsutil / FileID | ❌ | ❌ | ❌ | ❌ | ❌ |
| ERROR/INVALID 分离 | ✅ | ❌ 只有 PASS/FAIL | ✅ | ✅ | ✅ |
| 清理属性位复位 | ✅ | ❌ | ❌ | ✅ | ❌ |
| 清理 junction 用 rmdir | — | ✅ | ❌ | — | — |
| 环境清理拒绝卷根 | ✅ | ❌（`SilentlyContinue`） | ✅ | ✅ | ✅ |
| 判定强度档位 | 中（位模型） | **中高（零副作用 + 写穿检测）** | **中高（4 类链接 + 对抗性文件名）** | **中高（字节级 ADS）** | 中（内容隔离 + 属性位） |

**最强三题（按 Windows 绑定强度）**：`017`（4 类重解析点 + 内部链接 + 文件符号链接诱饵）> `007`（源/目标双侧 junction + preflight 零副作用）≈ `024`（ADS 三层独立验证 + 字节级编码）。
**最可改进**：`037`（补 FileID/链接数断言即可上探一档）、`031`/`024`（补 NTFS 卷断言与机制能力探测）。
