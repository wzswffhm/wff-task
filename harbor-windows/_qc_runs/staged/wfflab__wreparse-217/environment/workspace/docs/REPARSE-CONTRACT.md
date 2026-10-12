# WReparse 行为契约（权威规格）

> 本文件是 `WReparse` 模块的**唯一权威行为规格**。`instruction.md`、`environment/**`
> 与 `tests/**` 都围绕本契约表达同一份意图；三者出现分歧时以本文件为准。

## 1. 背景

`WReparse` 是磁盘治理流水线中负责「安全遍历 + 重解析点审计」的 PowerShell 模块。
它被用于对来源不明的目录树做只读盘点：必须在**不越界**的前提下把整棵树枚举清楚，
并把所有 NTFS 重解析点（junction、符号链接、挂载点）单独登记出来，交给下游做保留 /
清理决策。

历史事故的根因集中在两类：一类是遍历器悄悄跟随了 reparse point，越出扫描根目录读到了
无关数据；另一类是登记结果依赖枚举顺序或宿主区域设置，同一棵树在两台机器上产出不同的
报告，导致下游比对全部失效。本契约把这两类行为钉死。

## 2. 公共 API

模块必须导出且仅导出以下函数（名字与参数名逐字一致）：

| 函数 | 说明 |
| --- | --- |
| `Get-WReparseReport` | `-Root <string>`（必填）、`-MaxDepth <int>`（默认 32）、`-Follow`（开关，默认关）→ 返回报告对象 |
| `ConvertTo-WReparseJson` | `-Report <object>`（必填）→ 返回该报告的 JSON 字符串 |
| `Get-WReparseSchemaVersion` | 无参数 → 返回 `wreparse/1.0` |
| `Test-WReparseWithinRoot` | `-Path <string>`、`-Root <string>` → 返回该路径是否落在根目录**之内**（含根本身） |
| `Get-WReparseCanonicalPath` | `-Path <string>` → 返回规范化后的绝对路径 |
| `Resolve-WReparseLinkTarget` | `-LinkFullPath <string>`、`-RawTarget <string>` → 返回解析后的绝对目标路径，无法解析时返回 `$null` |

## 3. 报告数据模型

`Get-WReparseReport` 返回一个对象，字段顺序固定为：

```
SchemaVersion : string      # 恒为 'wreparse/1.0'
Root          : string      # 规范化后的扫描根绝对路径
Records       : object[]    # 见 3.1，始终是数组（空时是空数组，不是 $null）
Errors        : object[]    # 见 3.2，始终是数组
Stats         : object      # 见 3.3
```

### 3.1 Record

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `RelativePath` | string | 相对扫描根的路径，分隔符为 `\`；根自身不产生记录 |
| `Kind` | string | `Directory` / `File` / `ReparsePoint` 三选一 |
| `ReparseKind` | string 或 `null` | 仅当 `Kind` 为 `ReparsePoint` 时非空：`SymbolicLink` / `Junction` / `MountPoint` / `Unknown` |
| `Target` | string 或 `null` | 仅 reparse 条目：磁盘上**原样**记录的目标串（可能是相对路径）；其余为 `null` |
| `ResolvedTarget` | string 或 `null` | 仅 reparse 条目：按 §5.3 解析出的绝对路径；无法解析为 `null`；其余为 `null` |
| `InScope` | bool | 仅 reparse 条目有意义：`ResolvedTarget` 是否落在扫描根之内；其余恒为 `false` |
| `Depth` | int | 扫描根的**直接子项为 1**，逐层 +1 |
| `Size` | int64 | 文件为字节长度；目录与 reparse 条目为 0 |

判断条目是否为 reparse 点，只能依据文件属性中的 `FILE_ATTRIBUTE_REPARSE_POINT`。
**硬链接不是 reparse 点**：它没有该属性，必须按普通 `File` 登记（即使其链接类型显示为
`HardLink`）。

### 3.2 Error

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `RelativePath` | string | 出错位置；扫描根自身出错时为 `.` |
| `Code` | string | 见 §7 |
| `Message` | string | 人类可读说明，不参与判定 |

### 3.3 Stats

| 字段 | 含义 |
| --- | --- |
| `Directories` | `Kind` 为 `Directory` 的记录数 |
| `Files` | `Kind` 为 `File` 的记录数 |
| `ReparsePoints` | `Kind` 为 `ReparsePoint` 的记录数 |
| `Skipped` | 因未跟随而**没有进入**的 reparse 点数量 |
| `Errors` | `Errors` 数组长度 |

三个类别计数互斥且必须与实际记录一致；`Directories + Files + ReparsePoints` 等于记录总数。

## 4. 遍历语义

1. **默认不跟随**：未给 `-Follow` 时，遇到 reparse 点只登记该条目本身，**绝不进入**其目标，
   并把 `Skipped` 加一。
2. **跟随模式**（`-Follow`）：对每个 reparse 点，先按 §5.3 解析目标：
   - 目标无法解析，或解析结果在磁盘上不存在 → 记 `broken_target`，不进入；
   - 目标解析结果已出现在**当前分支的祖先链**上 → 记 `cycle`，不进入；
   - 目标存在且不构成循环，且是目录 → 进入，其下条目仍以**链接路径**为前缀命名
     （例如 `link-in\readme.txt`），而不是以真实目标路径命名；
   - 目标是文件 → 只登记链接条目，不产生子项。
3. **深度**：`Depth` 从 1 起算（见 §3.1）。某目录的 `Depth` 已达到 `-MaxDepth` 时，
   不再枚举其子项，并为该目录记一条 `too_deep`。`-MaxDepth` 小于 0 时按 0 处理。
4. **失败隔离**：单个目录枚举失败不得中断整次扫描，其余分支必须照常产出记录。
5. 扫描根本身不产生 `Record`。

## 5. 路径语义

### 5.1 规范化

`Get-WReparseCanonicalPath` 必须：展开为绝对路径、折叠 `.` 与 `..`、去掉末尾分隔符；
但**卷根**（`C:\`）与 **UNC 共享根**（`\\server\share`）保留其形态。大小写原样保留。

### 5.2 边界判定

`Test-WReparseWithinRoot` 必须按**目录边界**判断，而不是字符串前缀：

- `C:\root` 与 `C:\root2` 是**两个不同的目录**，后者不在前者之内；
- 比较使用**序数、忽略大小写**（Windows 路径语义）；
- 路径等于根时视为在内。

### 5.3 链接目标解析

`Resolve-WReparseLinkTarget`：

- 目标为**绝对路径** → 直接规范化；
- 目标为**相对路径** → 相对**链接自身所在目录**解析。**不得**相对进程当前工作目录，
  也**不得**相对扫描根解析；
- 目标为空或无法规范化 → 返回 `$null`。

## 6. 排序与确定性

1. `Records` 必须按 `RelativePath` 排序，主键为**序数、忽略大小写**；主键相同时以
   **序数、区分大小写**决胜，保证结果稳定。
2. **不得**使用受宿主区域设置（culture）影响的默认排序。
3. `Errors` 亦须稳定排序（先按 `RelativePath`，再按 `Code`），比较规则同上。
4. 同一棵树、同一参数连续两次调用，`ConvertTo-WReparseJson` 的输出必须**逐字节相同**。
   报告不得包含时间戳、进程号、随机值或机器相关字段。

## 7. 错误码

| Code | 触发条件 |
| --- | --- |
| `not_found` | 扫描根不存在（`RelativePath` 为 `.`） |
| `access_denied` | 枚举某目录失败 |
| `cycle` | `-Follow` 下目标构成祖先环 |
| `broken_target` | `-Follow` 下目标无法解析或不存在 |
| `structure` | 扫描根存在但不是目录 |
| `too_deep` | 某目录已达 `-MaxDepth`，未枚举其子项 |
| `invalid_argument` | 扫描根字符串无法规范化 |

未给 `-Follow` 时，不得产生 `cycle` 与 `broken_target`。

## 8. 序列化

`ConvertTo-WReparseJson` 使用 `ConvertTo-Json`，`-Depth` 至少 12；`null` 字段必须序列化为
JSON `null`，空数组序列化为 `[]`。键顺序与 §3 一致。

## 9. 非目标

- 不修改、不删除、不创建任何被扫描的条目（只读）。
- 不跨越卷去解析挂载点内容（未给 `-Follow` 时一律不进入）。
- 不追求读取 reparse 点的原始字节（`FSCTL_GET_REPARSE_POINT`）；契约只要求登记
  目标路径与分类。
- 不承诺在非 Windows 平台上的行为。
