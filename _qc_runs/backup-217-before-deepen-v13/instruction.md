# WReparse：NTFS 重解析点的安全遍历与确定性审计

## 背景

磁盘治理流水线要对来源不明的目录树做**只读盘点**：在不越界的前提下把整棵树枚举清楚，
并把所有 NTFS 重解析点（junction、符号链接、挂载点）单独登记出来，交给下游做保留或清理决策。

上线之后出现两类事故，根因都在遍历与登记环节：

1. 遍历器会悄悄跟随重解析点，越出扫描根目录读到无关数据；
2. 同一棵树在不同机器上产出不同的报告，导致下游比对全部失效。

`environment/workspace/WReparse` 是当前实现。行为依据有两个来源，分工明确：

- `environment/workspace/docs/REPARSE-CONTRACT.md` 规定**语义**（字段含义、遍历规则、
  路径判定、错误码、序列化要求），语义层面以它为准；
- `environment/workspace/assets/observed-provider-facts.json` 是在真机
  （Windows 11 + NTFS + Windows PowerShell 5.1）上实测采集的 **provider 层权威事实**
  （属性与 `LinkType` 的真实取值、`.Target` 的实际类型、枚举顺序与排序规则的关系等）。
  **两者在实现细节上冲突时，以实测事实为准。**

当前实现与以上两个来源之间存在多处偏差，需要全部修掉。

## 目标

在不改变模块公共 API 名称、参数名与报告数据模型的前提下，让 `WReparse` 模块的输出
完全符合 `docs/REPARSE-CONTRACT.md`。要修改的文件位于 `environment/workspace/WReparse/`。

## 必须满足的行为

1. **公共 API**：模块导出且仅导出契约 §2 列出的六个函数，函数名与参数名逐字一致。
   `Get-WReparseReport` 接受 `-Root`（必填）、`-MaxDepth`（默认 32）、`-Follow`（开关，默认关）。
2. **报告模型**：返回对象字段与顺序符合契约 §3；`Records` 与 `Errors` 恒为数组；
   `Kind` 只取 `Directory` / `File` / `ReparsePoint`；非重解析条目的
   `ReparseKind` / `Target` / `ResolvedTarget` 必须是 `null`，序列化后是 JSON `null` 而不是 `""`。
3. **条目分类**：只有带 `FILE_ATTRIBUTE_REPARSE_POINT` 属性的条目才算 `ReparsePoint`。
   硬链接没有该属性，必须按普通 `File` 登记；junction 与符号链接必须给出**不同**的 `ReparseKind`。
4. **遍历语义**：默认不进入任何重解析目标，只登记条目本身并累计 `Stats.Skipped`；
   只有显式 `-Follow` 时才解析目标，并对祖先环记 `cycle`、对无法解析或不存在的目标记
   `broken_target`。`Depth` 从 1 起算（扫描根的直接子项为 1）。
5. **路径语义**：`Test-WReparseWithinRoot` 按**目录边界**判定（`C:\root` 不包含 `C:\root2`）；
   `Resolve-WReparseLinkTarget` 对相对目标按**链接自身所在目录**解析，不得按进程当前目录，
   也不得按扫描根；`Get-WReparseCanonicalPath` 保留输入的原始大小写并去掉末尾分隔符。
6. **排序与确定性**：`Records` 按 `RelativePath` 以「序数、忽略大小写」为主键、
   以「序数、区分大小写」决胜排序；`Errors` 同样稳定排序；同一棵树、同一参数连续两次
   序列化必须**逐字节相同**——报告里不得包含时间戳、进程号、随机值等易变字段。
7. **统计**：`Stats.Directories` / `Files` / `ReparsePoints` 三者互斥，分别等于对应 `Kind`
   的记录数，且总和等于记录总数；`Stats.Skipped` 等于因未跟随而没有进入的重解析点数量。
8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致（含 `invalid_argument`）；
   未给 `-Follow` 时不得产生 `cycle` 与 `broken_target`。
9. **导出面**：模块**只**导出契约 §2 的六个函数。内部辅助函数（遍历、排序、
   记录构造等）不得出现在模块的可见命令面上。
10. **报告字段集合**：报告对象的字段**恰好**是契约 §3 的 `SchemaVersion` / `Root` /
    `Records` / `Errors` / `Stats` 五项，不得多出任何字段（包括生成时间戳之类的元数据）。
11. **排序与宿主区域设置无关**：`Records` 与 `Errors` 的比较键必须是**序数**比较。
    不得把排序委托给受宿主 culture 影响的默认排序——在含非 ASCII 名字的目录上，
    这种排序会按基字母重排，使同一棵树在不同宿主机上产出不同报告。
12. **记录字段的类型稳定**：`Target` 是一个目标串。provider 可能把目标返回成集合，
    且 PowerShell 转发单元素数组时会退化成元素本身；实现必须显式把它规范成字符串，
    不得让 `Target` 的类型随目标个数变化。

## 边界和约束

- 平台：Windows + Windows PowerShell 5.1 + NTFS。不得依赖管理员权限。
- 网络：不需要网络，也不应发起网络请求。
- 只读：扫描过程不得创建、修改或删除被扫描的条目。
- 允许修改 `environment/workspace/WReparse/**`。
- **不得修改** `tests/**`、`environment/**` 下的驱动脚本，以及
  `environment/workspace/docs/REPARSE-CONTRACT.md`。
- 不引入外部依赖：保持纯 PowerShell + .NET BCL。
- 模块必须在 Windows PowerShell 5.1 下可正常导入并运行（不得要求 PowerShell 7）。
- `environment/workspace/assets/observed-provider-facts.json` 是只读的权威事实，
  不得修改；`environment/workspace/tests/test_wreparse_basic.ps1` 是可见冒烟测试，
  也不得修改。

## 运行入口

评测在独立的评测环境中进行：评测方先准备一棵固定的 NTFS 目录树（含普通文件、目录、
junction、符号链接、硬链接，以及循环、悬空目标和名字前缀相似的兄弟目录等边界情形），
再对模块公共 API 运行一组契约一致性检查，结果写入 `results/result.json`。

`environment/workspace/tests/test_wreparse_basic.ps1` 是**可见冒烟测试**：它只确认
模块能导入、报告结构存在、能序列化。它**不**校验上面任何一条细则，
通过它**不代表**实现了契约——当前这份有偏差的实现同样能通过它。

所述评测夹具与检查脚本属于**评测资产，不提供给候选**。请严格按
`docs/REPARSE-CONTRACT.md` 实现语义，并逐条核对这些边界情形：普通文件与目录、junction 与
符号链接（两者 `ReparseKind` 必须不同）、硬链接（必须按普通文件登记）、相对目标链接、
指向扫描根之外的链接、循环链接与悬空目标、仅前缀相同的兄弟目录、**目标为文件的链接**、
**指向同一目标的兄弟链接**、**空目录**，以及同一棵树重复序列化的一致性。

## 用户可见验收

1. 在夹具树上调用 `Get-WReparseReport -Root <scanroot>`：每个重解析点都被登记但都没有被进入，
   且 `Stats.Skipped` 等于重解析点数量。
2. 检查与扫描根只共享名字前缀的兄弟目录上的那个链接：对应记录的 `InScope` 为 `false`；
   指向扫描根内部的链接 `InScope` 为 `true`。
3. 对同一条相对符号链接，`ResolvedTarget` 等于「链接所在目录 + 目标」，与进程当前工作目录无关。
4. 连续两次调用 `Get-WReparseReport` 并序列化，两次 JSON 字符串完全相同。
5. `hardlink.txt` 的 `Kind` 为 `File`；junction 与符号链接的 `ReparseKind` 分别是
   `Junction` 与 `SymbolicLink`。
6. 扫描根不存在时报 `not_found`，扫描根是文件时报 `structure`；扫描根字符串无法规范化时报
   `invalid_argument`。
7. `-MaxDepth` 传负数与传 0 的行为**完全一致**（两者都对扫描根的直接子项报 `too_deep`）。
8. `-Follow` 下经链接进入的条目，其 `RelativePath` 以**链接路径**为前缀（例如 `link-in\readme.txt`），
   而不是以真实目标路径命名。
9. `-Follow` 下目标为**文件**的链接只登记链接条目自身，不产生任何子项。
10. 同一个目标被**兄弟分支**上的两个链接分别指向时**不构成环**：两个分支都应被正常进入，
    且 `Errors` 中不得出现针对它们的 `cycle`。
11. 扫描一棵**空目录**树时，序列化结果中 `Records` 与 `Errors` 均为 `[]`。
12. 导入模块后，可见函数恰好是 `Get-WReparseReport`、`ConvertTo-WReparseJson`、
    `Get-WReparseSchemaVersion`、`Test-WReparseWithinRoot`、`Get-WReparseCanonicalPath`、
    `Resolve-WReparseLinkTarget` 六个；内部辅助函数（如遍历与排序函数）不可见。
13. 报告对象不含 `SchemaVersion` / `Root` / `Records` / `Errors` / `Stats` 之外的字段。
14. 在名字含非 ASCII 字符（如 `Ä`、`ö`）的目录上，`Records` 仍严格按**序数**规则排序：
    例如 ASCII 的 `Z` 必须排在 `Ä` 与 `ö` 之前——按基字母排序的实现会给出相反结果。
15. 未给 `-Follow` 时，报告的 `Errors` 中不出现 `cycle` 与 `broken_target`，
    即使扫描树里存在环和悬空目标。
16. 普通文件与目录（如 `plain.txt`、`docs`、硬链接）的 `InScope` 恒为 `false`；
    `InScope` 只对重解析点条目有意义。
17. 任何重解析点条目的 `Target` 都是字符串类型，不因目标个数而变化。
