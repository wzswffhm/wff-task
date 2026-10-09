按 docs/REPARSE-CONTRACT.md 与 assets/observed-provider-facts.json 修复了 WReparse 模块的全部偏差，只改动 WReparse/ 下的五个实现文件：

**Model.ps1**
- 移除报告中的 `GeneratedAt` 时间戳字段：报告恰好是 SchemaVersion/Root/Records/Errors/Stats 五字段，保证两次序列化逐字节相同。

**PathSemantics.ps1**
- `Get-WReparseCanonicalPath`：不再 `.ToLowerInvariant()`，保留输入原始大小写；卷根 `C:\` 保留末尾分隔符形态（UNC 共享根亦不破坏）。
- `Test-WReparseWithinRoot`：改为目录边界判定（等根或 `root\` 前缀，OrdinalIgnoreCase），`C:\root2` 不再误判在 `C:\root` 内。
- `Resolve-WReparseLinkTarget`：相对目标改为按链接自身所在目录（Split-Path -Parent $LinkFullPath）解析，不再用进程当前目录；空目标或规范化失败返回 $null。

**Walker.ps1**
- `Test-WReparseIsReparsePoint`：改用 Attributes 的 FILE_ATTRIBUTE_REPARSE_POINT 位判定（实测事实：硬链接 LinkType=HardLink 但无此属性），硬链接正确按 File 登记。
- `Get-WReparseKindFromLinkType`：Junction 不再错映射为 SymbolicLink，Junction/SymbolicLink/MountPoint/Unknown 各自区分。
- 新增 `ConvertTo-WReparseTargetString`：显式把 provider 的集合型 .Target 规范为首元素字符串，Target 类型稳定为 String。
- 遍历语义：未 -Follow 时只登记 + Skipped++，绝不产生 cycle/broken_target；-Follow 时才解析并进入，broken_target（无法解析/不存在）、cycle（仅当前分支祖先链，兄弟链接共指同一目标不构成环）；进入链接目标时以链接路径为虚拟前缀（link-in\readme.txt）；目标是文件的链接不产生子项；Follow 开关不再被硬编码为 true。
- 记录 Depth 从 1 起算（修正为传 childDepth）；普通文件/目录 InScope 恒为 false。
- MaxDepth 负数 clamp 为 0；Depth≥1 且达到上限的目录记 too_deep 且不枚举其子项（根始终枚举，故 MaxDepth=0 与负数行为一致：登记直接子项并对其中目录报 too_deep）。
- 根无法规范化时返回 invalid_argument 错误（此前被静默吞掉）。

**Audit.ps1**
- Records 改用已有的序数稳定归并排序 Sort-WReparseStable（主键 OrdinalIgnoreCase、决胜 Ordinal），弃用 culture 敏感的 Sort-Object；Errors 按 (RelativePath, Code) 同样序数稳定排序（新增 TieBreakSelector）。
- `Get-WReparseStats`：Directories/Files/ReparsePoints 三者互斥计数（此前 ReparsePoint 被重复计入 Directories）。

**WReparse.psm1 / WReparse.psd1**
- 导出面收敛为契约 §2 的恰好六个函数，内部辅助函数（遍历、排序、工厂等）不再可见。

在 Windows PowerShell 5.1 真机上用含 junction、相对/绝对符号链接、硬链接、悬空目标、指回祖先的环、兄弟共指链接、指根外链接、非 ASCII 目录名、空目录、拒绝访问目录的夹具树逐条验证了 17 条用户可见验收（含两次序列化逐字节一致、Z 排在 Ä/ö 前、not_found/structure/invalid_argument、access_denied 隔离等），全部通过；可见冒烟测试亦通过。未触碰 tests/、docs/、assets/，仓库内无临时文件残留。