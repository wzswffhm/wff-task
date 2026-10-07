# WReparse：NTFS 重解析点的安全遍历与确定性审计

## 背景

磁盘治理流水线要对来源不明的目录树做**只读盘点**：在不越界的前提下把整棵树枚举清楚，
并把所有 NTFS 重解析点（junction、符号链接、挂载点）单独登记出来，交给下游做保留或清理决策。

上线之后出现两类事故，根因都在遍历与登记环节：

1. 遍历器会悄悄跟随重解析点，越出扫描根目录读到无关数据；
2. 同一棵树在不同机器上产出不同的报告，导致下游比对全部失效。

`environment/workspace/WReparse` 是当前实现，`environment/workspace/docs/REPARSE-CONTRACT.md`
是它的**唯一权威行为规格**。当前实现与契约之间存在多处偏差，需要全部修掉。

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
8. **错误码**：只使用契约 §7 的七个码，触发条件与契约一致；未给 `-Follow` 时不得产生
   `cycle` 与 `broken_target`。

## 边界和约束

- 平台：Windows + Windows PowerShell 5.1 + NTFS。不得依赖管理员权限。
- 网络：不需要网络，也不应发起网络请求。
- 只读：扫描过程不得创建、修改或删除被扫描的条目。
- 允许修改 `environment/workspace/WReparse/**`。
- **不得修改** `tests/**`、`environment/**` 下的驱动脚本，以及
  `environment/workspace/docs/REPARSE-CONTRACT.md`。
- 不引入外部依赖：保持纯 PowerShell + .NET BCL。
- 模块必须在 Windows PowerShell 5.1 下可正常导入并运行（不得要求 PowerShell 7）。

## 运行入口

评测在独立的评测环境中进行：评测方先准备一棵固定的 NTFS 目录树（含普通文件、目录、
junction、符号链接、硬链接，以及循环、悬空目标和名字前缀相似的兄弟目录等边界情形），
再对模块公共 API 运行一组契约一致性检查，结果写入 `results/result.json`。

所述夹具与检查脚本属于**评测资产，不提供给候选**。请严格按
`docs/REPARSE-CONTRACT.md` 实现语义，并逐条核对这些边界情形：普通文件与目录、junction 与
符号链接（两者 `ReparseKind` 必须不同）、硬链接（必须按普通文件登记）、相对目标链接、
指向扫描根之外的链接、循环链接与悬空目标、仅前缀相同的兄弟目录，以及同一棵树重复
序列化的一致性。

## 用户可见验收

1. 在夹具树上调用 `Get-WReparseReport -Root <scanroot>`：每个重解析点都被登记但都没有被进入，
   且 `Stats.Skipped` 等于重解析点数量。
2. 检查与扫描根只共享名字前缀的兄弟目录上的那个链接：对应记录的 `InScope` 为 `false`；
   指向扫描根内部的链接 `InScope` 为 `true`。
3. 对同一条相对符号链接，`ResolvedTarget` 等于「链接所在目录 + 目标」，与进程当前工作目录无关。
4. 连续两次调用 `Get-WReparseReport` 并序列化，两次 JSON 字符串完全相同。
5. `hardlink.txt` 的 `Kind` 为 `File`；junction 与符号链接的 `ReparseKind` 分别是
   `Junction` 与 `SymbolicLink`。
6. 扫描根不存在时报 `not_found`，扫描根是文件时报 `structure`。
