## 修改概览

修复了 `WReparse` 模块相对 `docs/REPARSE-CONTRACT.md` 与 `assets/observed-provider-facts.json` 的全部偏差，共改动 6 个文件（仅实现代码）。

### Model.ps1
- **删除 `GeneratedAt`**：这是破坏确定性的根因，报告现在恰好是契约 §3 的五个字段。
- `New-WReparseRecord` 强制不变量：非 `ReparsePoint` 条目的 `ReparseKind`/`Target`/`ResolvedTarget` 一律为 `$null`、`InScope` 为 `false`；新增 `ConvertTo-WReparseOptionalString` 把 provider 可能返回的集合显式取首元素并转成 `string`（空串归一为 `null`，序列化成 JSON `null` 而非 `""`）。

### PathSemantics.ps1
- `Get-WReparseCanonicalPath` **去掉 `ToLowerInvariant()`**（契约要求原样保留大小写）；卷根保留 `C:\`，UNC 共享根规范成 `\\server\share`。
- `Test-WReparseWithinRoot` 从字符串前缀改为**目录边界**判定：拼接分隔符后再比较，`C:\root2` 不再被判为落在 `C:\root` 内。
- `Resolve-WReparseLinkTarget` 相对目标改为按**链接自身所在目录**解析（原实现直接 `GetFullPath`，等于按进程当前目录）；顺带剥离 junction 可能出现的 `\??\` 前缀。

### Walker.ps1
- `Test-WReparseIsReparsePoint` 改为检查 **`FILE_ATTRIBUTE_REPARSE_POINT` 属性位**而非 `LinkType` 非空——后者会把 `LinkType='HardLink'` 的硬链接误判成重解析点。
- `Get-WReparseKindFromLinkType`：`Junction` 原先被错映射成 `SymbolicLink`，现在两者是不同的 `ReparseKind`。
- **`Follow` 原先硬编码为 `$true`**，现按 `FollowMode` 取值；未给 `-Follow` 时只登记并累加 `Skipped`，不再产生 `cycle`/`broken_target`。
- `Depth` 从 1 起算（原先给子项传的是父深度）。
- 跟随时递归传入的是**链接的相对路径前缀**（原先传真实目标路径），所以经链接进入的条目命名为 `link-in\readme.txt`；改用 `RelativePrefix` 逐层拼接，避免对虚拟路径做规范化往返。
- 环检测用祖先链 + 序数忽略大小写比较，兄弟分支指向同一目标不再误报 `cycle`；目标为文件时只登记链接自身。
- 深度门禁从「函数入口」移到「下降点」：`too_deep` 记在达到上限的**那个子目录**上，使 `-MaxDepth 0` 与负数行为完全一致（均对扫描根直接子项报错）。
- 根无法规范化时产出 `invalid_argument`（原先静默返回空对象，该错误码从未被使用过）。

### Audit.ps1
- 原先定义了 `Sort-WReparseStable` 却实际走 `Sort-Object`（culture 敏感）。现在记录与错误都走**序数稳定归并排序**；记录按 `RelativePath`，错误按 `RelativePath` 再 `Code`（原先只按 `Code`）。
- `Get-WReparseStats` 修正为三类互斥计数（原先把 reparse 同时计入 `Directories`，总和不等于记录数）。

### WReparse.psm1 / .psd1
- 把 `Export-ModuleMember -Function *` 与清单的 `FunctionsToExport = '*'` 收窄为契约 §2 的六个函数，内部辅助函数不再出现在命令面上。

## 验证

在沙箱内用 Windows PowerShell 5.1（5.1.26100）建了一棵真实 NTFS 夹具树（junction、符号链接、硬链接、相对/悬空/循环/越界目标、仅前缀相同的兄弟目录 `scanroot2`、非 ASCII 名字、空目录），逐条核对：

- 默认模式：7 个重解析点全部登记且均未进入，`Skipped == ReparsePoints`；`Errors` 无 `cycle`/`broken_target`。
- `junction-out`（指向 `scanroot2`）`InScope=false`，根内链接 `InScope=true`；普通文件/目录/硬链接恒 `false`。
- `-Follow`：`junction-in\readme.txt` 以链接为前缀；`symlink-file` 无子项；`junction-cycle` 报 `cycle`、`symlink-broken` 报 `broken_target`；指向 `docs` 的兄弟链接未误报环。
- 相对链接 `ResolvedTarget` 在两个不同 CWD 下结果一致。
- 两次序列化 `-ceq` 逐字节相同；`MaxDepth 0` 与 `-1` 输出相同。
- `not_found` / `structure` / `invalid_argument` 均按预期触发。
- 排序为 `Zz < Ä < ö`（序数），`hardlink.txt` 的 `Kind` 为 `File`。
- 导出面恰好 6 个函数，8 个内部函数均不可见。
- 可见冒烟测试 `tests/test_wreparse_basic.ps1` 全部通过。

未改动 `tests/**`、`environment/**`、契约与实测事实文件；`git status` 仅显示上述 6 个实现文件，临时夹具建在 `%TEMP%` 并已清理。

一处判断需要说明：契约 §4.3 说「某目录的 `Depth` 已达 `-MaxDepth` 时…为该目录记一条 `too_deep`」，而验收条款 7 要求 `-MaxDepth 0` 与负数「都对扫描根的直接子项报 `too_deep`」。由于扫描根本身不产生记录、也就没有 `Depth`，我按条款 7 的字面行为实现（门禁在下降点，`too_deep` 归属子目录）；代价是 `-MaxDepth 1` 与 `0` 行为相同——契约只要求 0 与负数一致，未约束这一点。