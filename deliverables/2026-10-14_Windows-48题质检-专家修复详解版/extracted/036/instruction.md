# 注册表配置补丁的事务修复

桌面客户端升级时要更新当前用户的一棵注册表配置树。现有 `RegistryPatchApplier.ps1` 能读值并完成部分预演，实际写入和事务处理还不完整。升级需要可靠的整批更新、预演和回滚，请按下面的契约修好这个工具。只修改工作区的 `RegistryPatchApplier.ps1`，运行环境是 Windows Server 2022 x64、PowerShell 7.4.18；不联网、不安装模块，也不需要管理员权限。

入口是 `pwsh -NoProfile -File .\RegistryPatchApplier.ps1 -PatchPath patch.json -ReportPath report.json`，另有 `-Preview`、`-Atomic`。UTF-8 JSON 补丁包含字符串 `Root`（`HKCU:\` 下的非空路径）和数组 `Operations`。每项有字符串 `Path`、`Name`、`Action`；`Path` 是根下的相对键路径，空串表示根键，`Name` 空串表示默认值。键和值名忽略大小写，字符按字面处理；不接受 `.`、`..`、绝对 Path、冒号或 NUL。目标键必须已经存在，工具不创建或删除键。操作顺序与清单一致，报告保留清单里的 Path/Name 文本。

`Set` 和 `Assert` 还需 `Type`、`Value`。String/ExpandString 的 Value 是字符串，ExpandString 中 `%变量%` 保存、比较和恢复时都是原文；DWord 是 0..4294967295 的 JSON 整数，读写按 32 位无符号位模式；QWord 是 -9223372036854775808..9223372036854775807 的十进制字符串；Binary 是 0..255 整数数组；MultiString 是字符串数组。两种数组允许空数组，字符串允许空串。比较同时检查注册表类型与完整内容，字符串比较区分大小写，数组按元素顺序比较。`Delete` 只删除指定值，值原本不存在属于 Unchanged；`Assert` 只检查，缺值、类型或内容不符均失败。相同类型和内容的 Set 也属于 Unchanged。

普通模式遇到不存在或不可访问的键、断言失败或写入失败时，记下该项 Failed，并继续后面的操作。原子模式先检查整批目标键是否存在且可写，任何一项不合格都不落盘：问题项 Failed，其余 Skipped。检查通过后按顺序执行；操作失败就把本批已改变的值恢复到执行前的存在性、类型和完整内容，成功恢复的项记为 RolledBack，失败项 Failed，后续项 Skipped，原来未改变的项仍是 Unchanged/AssertPassed。原子模式中重复目标（完整键路径和值名忽略大小写）是补丁错误；普通模式允许重复，并让后面的操作看到前面的结果。回滚也失败时，该项记 RollbackFailed 并提供 Error，退出码仍为 2。不能改动未提到的键和值。

Preview 根据每个目标在调用开始时的状态报告 WouldSet、WouldDelete、Unchanged 或 AssertPassed/Failed，Applied 和所有 Changed 都是 0/false，不允许注册表发生变化。Preview 与 Atomic 同用时仍按这个规则预演，但要拒绝重复目标。普通成功 Status=Succeeded，预演成功 Status=Previewed；存在操作失败、原子预检失败或回滚时 Status=Failed。报告包含 Processed（清单项数）、Applied（最终保留下来的实际变更项数）、Failed（Failed 或 RollbackFailed 项数）、RolledBack（恢复成功项数）和按原顺序排列的 Items；每项有 Path、Name、Action、Status、Changed，失败项还要有 Error。

全部操作成功退出 0，操作或回滚失败退出 2。参数、JSON 结构、值类型/范围、路径语法、原子重复目标或报告路径不可用退出 3，这类输入错误必须在任何注册表变更前被发现；能写报告时输出 Status=Failed、Processed=Applied=RolledBack=0、Failed=1、Items=[] 和顶层 Error。报告为 UTF-8 JSON，缺目录时创建；任何模式都不得静默成功或遗漏清单项。工作区的 smoke.ps1 能演示常规写入，完整边界请依据上述契约验证。
