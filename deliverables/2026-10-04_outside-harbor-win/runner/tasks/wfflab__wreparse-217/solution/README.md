# 参考实现（WReparse）

本目录是组织方用于 Golden 校验的隐藏参考答案，**不进入任何对外交付包**。

## 参考实现满足了什么契约

`reference/WReparse/` 是 `environment/workspace/WReparse/` 的完整替换版本，逐条满足
`environment/workspace/docs/REPARSE-CONTRACT.md`：

| 契约条目 | 参考实现的关键点 |
| --- | --- |
| §5.1 规范化 | 保留输入的原始大小写；只折叠 `.` / `..` 与末尾分隔符；卷根与 UNC 共享根保留形态 |
| §5.2 边界判定 | 比较前先按目录边界切分，再以序数、忽略大小写作主比较；`C:\root2` 不属于 `C:\root` |
| §5.3 目标解析 | 相对目标以**链接自身所在目录**为基准解析，不读进程当前目录、不读扫描根 |
| §3.1 分类 | 仅以 `FILE_ATTRIBUTE_REPARSE_POINT` 属性判定重解析点，因此硬链接保持 `File` |
| §3.1 链接种类 | 依据链接类型区分 `Junction` / `SymbolicLink` / `MountPoint` / `Unknown`，互不合并 |
| §4 遍历 | 默认不进入任何重解析目标并累计 `Skipped`；`-Follow` 才解析目标并报 `cycle` / `broken_target` |
| §3.1 深度 | `Depth` 从 1 起算 |
| §3.1 空值 | `ReparseKind` / `Target` / `ResolvedTarget` 在非重解析条目上保持真正的 `$null` |
| §6 排序与确定性 | 主键「序数、忽略大小写」+ 决胜「序数、区分大小写」；报告不含任何易变字段，两次序列化逐字节相同 |
| §3.3 统计 | `Directories` / `Files` / `ReparsePoints` 三类互斥，与记录一一对应 |
| §7 错误码 | 仅使用契约列出的七个错误码，触发条件一致 |

## 边界与不变式

- 只读：扫描过程不创建、不修改、不删除被扫描的条目。
- 无外部依赖：纯 PowerShell + .NET BCL，可在 Windows PowerShell 5.1 下导入。
- 公共 API 名称与参数名与契约 §2 完全一致，未新增导出函数。

## 使用方式

`solve.ps1` 会把 `reference/WReparse/` 镜像到 `environment/workspace/WReparse/`，用于
Oracle / Golden 控制跑。它可重复执行，且不产生网络请求或临时日志。
