# WReparse 行为契约（正式规格）

> 本文件规定 `WReparse` 模块的**语义**，`tests/**` 的契约一致性检查与本文件对齐。
>
> **本文件不给出实现规则。** §3–§7 只提供**实测得到的行为样例**（在真机
> Windows 11 + NTFS + Windows PowerShell 5.1 上跑出的真实输出），
> 期望的字段、类型、次序、深度与错误码**须由你从这些样例自行归纳**，
> 并与 `../assets/observed-provider-facts.json` 的实测事实交叉印证。
> 两者冲突时以实测事实为准。
>
> 同目录下的 `REPARSE-CONTRACT.draft.md` 是更早的草稿，来源与校准状态未知。

## 1. 背景

`WReparse` 是磁盘治理流水线中负责「安全遍历 + 重解析点审计」的 PowerShell 模块。
它被用于对来源不明的目录树做只读盘点：必须在**不越界**的前提下把整棵树枚举清楚，
并把所有 NTFS 重解析点（junction、符号链接、挂载点）单独登记出来，交给下游做保留 /
清理决策。

历史事故的根因集中在两类：一类是遍历器悄悄跟随了 reparse point，越出扫描根目录读到了
无关数据；另一类是登记结果依赖枚举顺序或宿主区域设置，同一棵树在两台机器上产出不同的
报告，导致下游比对全部失效。本契约把这两类行为钉死——**但钉法是给出观测样例，而非规则**。

## 2. 公共 API（骨架，不得更改）

模块必须导出且仅导出以下函数（名字与参数名逐字一致）：

| 函数 | 参数 |
| --- | --- |
| `Get-WReparseReport` | `-Root <string>`（必填）、`-MaxDepth <int>`（默认 32）、`-Follow`（开关，默认关） |
| `ConvertTo-WReparseJson` | `-Report <object>`（必填） |
| `Get-WReparseSchemaVersion` | 无参数 |
| `Test-WReparseWithinRoot` | `-Path <string>`、`-Root <string>` |
| `Get-WReparseCanonicalPath` | `-Path <string>` |
| `Resolve-WReparseLinkTarget` | `-LinkFullPath <string>`、`-RawTarget <string>` |

> 该表是**唯一**允许直接照抄的定义：它是接口签名，不含任何行为规则。

## 3. 报告结构样例

### 3.1 顶层字段顺序（实测）

```
SchemaVersion / Root / Records / Errors / Stats
```

`Get-WReparseSchemaVersion` 的返回值实测为 `wreparse/1.0`。

### 3.2 一条普通目录条目（实测）

```json
{
  "RelativePath": "beta",
  "Kind": "Directory",
  "ReparseKind": null,
  "Target": null,
  "ResolvedTarget": null,
  "InScope": false,
  "Depth": 1,
  "Size": 0
}
```

### 3.3 一条普通文件条目（实测，`beta.txt` 为 4 字节）

```json
{
  "RelativePath": "beta.txt",
  "Kind": "File",
  "ReparseKind": null,
  "Target": null,
  "ResolvedTarget": null,
  "InScope": false,
  "Depth": 1,
  "Size": 4
}
```

### 3.4 重解析点条目（实测，同一棵树上的八条）

```
link-dangling  ReparsePoint  SymbolicLink  Target="missing-target"   ResolvedTarget="C:\wreparse-fixture\scanroot\missing-target"  InScope=true   Depth=1  Size=0
link-file      ReparsePoint  SymbolicLink  Target="plain.txt"        ResolvedTarget="C:\wreparse-fixture\scanroot\plain.txt"      InScope=true   Depth=1  Size=0
link-in        ReparsePoint  Junction      Target="C:\wreparse-fixture\scanroot\docs"   ResolvedTarget="C:\wreparse-fixture\scanroot\docs"    InScope=true   Depth=1  Size=0
link-loop      ReparsePoint  Junction      Target="C:\wreparse-fixture\scanroot"        ResolvedTarget="C:\wreparse-fixture\scanroot"         InScope=true   Depth=1  Size=0
link-out       ReparsePoint  Junction      Target="C:\wreparse-fixture\outside"         ResolvedTarget="C:\wreparse-fixture\outside"          InScope=false  Depth=1  Size=0
link-prefix    ReparsePoint  Junction      Target="C:\wreparse-fixture\scanroot-extra"  ResolvedTarget="C:\wreparse-fixture\scanroot-extra"   InScope=false  Depth=1  Size=0
link-rel       ReparsePoint  SymbolicLink  Target="docs"             ResolvedTarget="C:\wreparse-fixture\scanroot\docs"          InScope=true   Depth=1  Size=0
link-twin      ReparsePoint  Junction      Target="C:\wreparse-fixture\scanroot\docs"   ResolvedTarget="C:\wreparse-fixture\scanroot\docs"    InScope=true   Depth=1  Size=0
```

另有 `hardlink.txt`（由 `New-Item -ItemType HardLink` 创建）在同一棵树中被登记为
`Kind="File"`、`ReparseKind=null`、`Size=4`、`Depth=1`。

### 3.5 Stats 与错误集合（实测，同一次未给 `-Follow` 的扫描）

```json
{ "Directories": 5, "Files": 10, "ReparsePoints": 8, "Skipped": 8, "Errors": 0 }
```

### 3.6 空树的完整序列化输出（实测）

```json
{
    "SchemaVersion":  "wreparse/1.0",
    "Root":  "C:\\...\\empty-dir",
    "Records":  [ ],
    "Errors":  [ ],
    "Stats":  {
                  "Directories":  0,
                  "Files":  0,
                  "ReparsePoints":  0,
                  "Skipped":  0,
                  "Errors":  0
              }
}
```

## 4. 遍历与深度样例

### 4.1 未给 `-Follow`（实测）

- 8 个重解析点全部登记、全部未进入（`Skipped: 8`），`Errors` 为空；
- 与扫描根只共享名字前缀的兄弟目录 `scanroot-extra\other.txt` **不出现**在 `Records` 中。

### 4.2 给了 `-Follow`（实测，同一棵树）

```json
{ "Directories": 8, "Files": 18, "ReparsePoints": 8, "Skipped": 0, "Errors": 2 }
```

`Errors` 恰为两条：

```json
{"RelativePath": "link-dangling", "Code": "broken_target", "Message": "The reparse target does not exist."}
{"RelativePath": "link-loop",     "Code": "cycle",         "Message": "The reparse target is an ancestor already visited on this branch."}
```

### 4.3 经链接进入后的条目命名（实测）

```
link-in\nested                 Depth=2  Size=0
link-in\readme.txt             Depth=2  Size=6
link-in\nested\deep.txt        Depth=3  Size=4
link-out\secret.txt            Depth=2  Size=6
link-rel\nested                Depth=2  Size=0
link-rel\readme.txt            Depth=2  Size=6
link-twin\nested               Depth=2  Size=0
```

（`link-twin` 与 `link-in` 指向同一个 `docs`；`link-rel` 的磁盘目标是相对串 `docs`；
`link-out` 指向扫描根之外。三者都进入了、都产生了子项，且 `Errors` 中没有 `cycle`。）

### 4.4 `-MaxDepth` 各值（实测，同一棵树）

| 参数 | Stats | Errors |
| --- | --- | --- |
| `-MaxDepth 0` | `{"Directories":0,"Files":0,"ReparsePoints":0,"Skipped":0,"Errors":1}` | `[{"RelativePath":".","Code":"too_deep","Message":"Depth limit of 0 reached; not enumerating."}]` |
| `-MaxDepth -1` | **与 `-MaxDepth 0` 逐字节相同** | 同上 |
| `-MaxDepth 1` | `{"Directories":4,"Files":6,"ReparsePoints":8,"Skipped":8,"Errors":4}` | 4 条 |

### 4.5 深度层次（实测）

```
scanroot\beta\zeta.txt        Depth=2
scanroot\data\sample.bin      Depth=2
scanroot\docs\nested\deep.txt Depth=3
scanroot\link-in              Depth=1
```

## 5. 路径语义样例

### 5.1 `Get-WReparseCanonicalPath`（实测）

| 输入 | 输出 |
| --- | --- |
| `C:\wreparse-fixture\outside` | `C:\wreparse-fixture\outside` |
| `C:\wreparse-fixture\outside\` （带尾分隔符） | `C:\wreparse-fixture\outside` |
| `C:\wreparse-fixture\outside\PLAIN.TXT`（磁盘上是 `outside`，内层原样） | `C:\wreparse-fixture\outside\PLAIN.TXT` |

### 5.2 `Test-WReparseWithinRoot`（实测，`-Root = C:\wreparse-fixture\scanroot`）

| `-Path` | 结果 |
| --- | --- |
| `C:\wreparse-fixture\scanroot\docs` | `True` |
| `C:\wreparse-fixture\scanroot` | `True` |
| `C:\wreparse-fixture\scanroot-extra` | **`False`** |

### 5.3 `Resolve-WReparseLinkTarget`（实测）

| `LinkFullPath` | `RawTarget` | 结果 |
| --- | --- | --- |
| `C:\...\scanroot\link-rel` | `docs` | `C:\wreparse-fixture\scanroot\docs` |

> 该样例的进程当前工作目录是题包目录，与结果无关；结果只与链接自身所在目录有关。

## 6. 排序与确定性样例

### 6.1 `Records` 的实测次序（同一棵树，未给 `-Follow`）

```
beta
beta.txt
beta\zeta.txt
data
data\sample.bin
docs
docs\nested
docs\nested\deep.txt
```

含非 ASCII 名字的条目实测次序（与上文同类样本一起排序时）：

```
Z.txt          Depth=1  Size=8
Ä.txt          Depth=1  Size=8
ö.txt          Depth=1  Size=8
```

> `assets` 中记录了这组名字在 `en-US` / `de-DE` / `ja-JP` 三种区域设置下的
> `Sort-Object` 实测差异，以及序数（ordinal）次序的实测结果——**两者必须一致**，
> 请自行比对后归纳实现。

### 6.2 重复调用（实测）

同树同参数连续两次 `Get-WReparseReport` + `ConvertTo-WReparseJson`，
两次输出**逐字节相同**（实测比较结果 `True`）。报告中不得出现时间戳、
进程号、随机值或机器相关字段。

## 7. 错误码（码名固定，触发时机见样例）

只允许以下七个码：

```
not_found / access_denied / cycle / broken_target / structure / too_deep / invalid_argument
```

实测样例：

```json
{"RelativePath": ".", "Code": "not_found",  "Message": "Scan root does not exist: C:\\...\\does-not-exist"}
{"RelativePath": ".", "Code": "structure",  "Message": "Scan root is not a directory: C:\\...\\outside\\secret.txt"}
{"RelativePath": ".", "Code": "too_deep",   "Message": "Depth limit of 0 reached; not enumerating."}
{"RelativePath": "link-dangling", "Code": "broken_target", "Message": "The reparse target does not exist."}
{"RelativePath": "link-loop",     "Code": "cycle", "Message": "The reparse target is an ancestor already visited on this branch."}
```

未给 `-Follow` 时，实测的 `Errors` 为空（即使树里有环与悬空目标）。

## 8. 序列化

`ConvertTo-WReparseJson` 的输出形如 §3.6 与 §5 的样例：键顺序与 §3.1 一致，
`null` 字段为 JSON `null`、空数组为 `[]`，`-Depth` 足够容纳最深层级（实测最深 3 层，
但 `-Follow` 下的嵌套更浅；取值须保证任意 `-MaxDepth` 下不被截断）。

## 9. 非目标

- 不修改、不删除、不创建任何被扫描的条目（只读）。
- 不跨越卷去解析挂载点内容（未给 `-Follow` 时一律不进入）。
- 不追求读取 reparse 点的原始字节（`FSCTL_GET_REPARSE_POINT`）；本契约只要求登记
  目标路径与分类。
- 不承诺在非 Windows 平台上的行为。

## 10. provider 细节与实测事实

本文件的样例**只覆盖一个夹具树**；provider 层返回值的真实形状会随 Windows 版本与
访问方式变化。真机实测的权威事实记录在 `assets/observed-provider-facts.json`，包括：

- 重解析点与硬链接在文件属性上的区别；
- provider 给出的 `LinkType` 取值集合；
- `.Target` 的实际类型与相对/绝对形态；
- PowerShell 转发单元素数组时的类型行为；
- 枚举顺序、三种区域设置下的 `Sort-Object` 差异与序数次序的实测结果。

**当本文件的文字与 `assets/observed-provider-facts.json` 的实测事实在实现细节上
冲突时，以实测事实为准。** 语义层面以本文件为准。
