# WReparse 行为契约（草稿）

> **DRAFT** —— 本文件由早期迭代留存，**未经真机实测校准**。
> 正式规格见 `REPARSE-CONTRACT.md`。若两者不一致，以正式契约为准；
> 若正式契约的实现细节与 `../assets/observed-provider-facts.json` 的实测事实冲突，以实测事实为准。

## 1. 背景

`WReparse` 是磁盘治理流水线中负责「安全遍历 + 重解析点审计」的 PowerShell 模块。
用于对来源不明的目录树做只读盘点：在**不越界**的前提下枚举整棵树，
并把 NTFS 重解析点（junction、符号链接、挂载点）单独登记出来。

## 2. 公共 API

模块必须导出且仅导出以下六个函数（名字与参数名逐字一致）：

| 函数 | 说明 |
| --- | --- |
| `Get-WReparseReport` | `-Root <string>`（必填）、`-MaxDepth <int>`（默认 32）、`-Follow`（开关，默认关） |
| `ConvertTo-WReparseJson` | `-Report <object>`（必填） |
| `Get-WReparseSchemaVersion` | 无参数 |
| `Test-WReparseWithinRoot` | `-Path <string>`、`-Root <string>` |
| `Get-WReparseCanonicalPath` | `-Path <string>` |
| `Resolve-WReparseLinkTarget` | `-LinkFullPath <string>`、`-RawTarget <string>` |

## 3. 报告数据模型

`Get-WReparseReport` 返回一个对象，字段顺序固定为六项：

```
SchemaVersion : string      # 恒为 'wreparse/1.0'
Root          : string      # 规范化后的扫描根绝对路径
GeneratedAt   : string      # 报告生成时刻（ISO-8601，便于下游排查）
Records       : object[]
Errors        : object[]
Stats         : object
```

### 3.1 Record

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `RelativePath` | string | 相对扫描根的路径，分隔符为 `\`；根自身不产生记录 |
| `Kind` | string | `Directory` / `File` / `ReparsePoint` 三选一 |
| `ReparseKind` | string 或 `null` | 仅 `Kind` 为 `ReparsePoint` 时非空 |
| `Target` | string 或 `null` | 磁盘上原样记录的目标串 |
| `ResolvedTarget` | string 或 `null` | 解析后的绝对路径 |
| `InScope` | bool | `ResolvedTarget` 是否在扫描根之内 |
| `Depth` | int | **扫描根本身为 0**，其直接子项为 1，逐层 +1 |
| `Size` | int64 | 文件为字节长度；目录与 reparse 条目为 0 |

### 3.2 Error

`RelativePath` / `Code` / `Message` 三项；`Message` 为人类可读说明，不参与判定。

### 3.3 Stats

`Directories` / `Files` / `ReparsePoints` / `Skipped` / `Errors`。

## 4. 条目判定

- provider 给出的 `LinkType` **非空即视为重解析点**：`Junction`、`SymbolicLink`、
  `MountPoint`、`HardLink` 都会给出非空 `LinkType`，据此可统一登记为 `ReparsePoint`
  并把 `HardLink` 归入 `ReparseKind = 'HardLink'`。
- `Attributes` 只作为补充信息，不参与重解析点判定。
- `.Target` 为集合时取**全部元素并以 `;` 连接**后写入 `Target`。

## 5. 遍历语义

1. **默认跟随**：`-Follow` 在草稿版本里**默认开启**，遇到 reparse 点直接进入目标，
   以获得更完整的资产视图；显式 `-NoFollow` 才只登记不进入。
2. 跟随模式下目标无法解析或不存在 → 记 `broken_target`；构成祖先环 → 记 `cycle`。
3. `Depth` 见 §3.1（根自身为 0）。某目录 `Depth` 达到 `-MaxDepth` 时不再枚举其子项，
   并记 `too_deep`。`-MaxDepth` 小于 0 时按 **1** 处理。
4. 扫描根本身不产生 `Record`。

## 6. 路径语义

- 规范化：展开为绝对路径、折叠 `.` 与 `..`、去掉末尾分隔符；卷根与 UNC 共享根保留形态。
  **大小写统一转小写**，便于跨平台比对。
- 边界判定：按**字符串前缀**比较即可（`C:\root` 的子树一定以 `C:\root` 开头）。
- 链接目标解析：绝对路径直接规范化；相对路径**相对进程当前工作目录**解析
  （这与 PowerShell `Resolve-Path` 的默认行为一致）。

## 7. 排序与确定性

1. `Records` 按 `RelativePath` 排序，直接使用 PowerShell 的 `Sort-Object`
   （默认语义已足够稳定，且可读性最好）。
2. `Errors` 同样用 `Sort-Object` 按 `RelativePath` 排序。
3. 报告含 `GeneratedAt` 时间戳，便于排查；下游按字段名取值，顺序无影响。

## 8. 错误码

| Code | 触发条件 |
| --- | --- |
| `not_found` | 扫描根不存在 |
| `access_denied` | 枚举某目录失败 |
| `cycle` | 跟随下目标构成祖先环 |
| `broken_target` | 跟随下目标无法解析或不存在 |
| `structure` | 扫描根存在但不是目录 |
| `too_deep` | 某目录已达 `-MaxDepth` |
| `invalid_argument` | 扫描根字符串无法规范化 |
| `permission_denied` | 与 `access_denied` 同义，二者可任选其一 |

## 9. 序列化

`ConvertTo-Json`，`-Depth` 至少 8；`null` 序列化为 JSON `null`，
空数组序列化为 `[]`。键顺序按 §3 定义。
