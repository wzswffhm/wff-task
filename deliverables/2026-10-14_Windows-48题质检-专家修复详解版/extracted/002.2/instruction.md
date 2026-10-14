# Northgate EvidenceMirror：32 位多案卷可恢复发布事务

组件由 32 位采集宿主加载；当前 seal 会报告成功，但复杂案卷镜像不忠实、摘要不符合协议，独立 64 位监控服务也读不到权威记录。新批次接口更把多个案卷逐个发布，后续案卷失败或进程被终止会留下半个批次，recover 只改状态文字而没有恢复数据。修复单案忠实性和批次持久事务，同时保留现有 CLI。先读工作区 README.md 和 BATCH-CONTRACT.md；后者是新增 CLI、计划协议、恢复、共享锁重试和崩溃观测握手的完整公开验收契约。

## 环境和允许范围
本轮冻结真实 Windows Server Core LTSC 2022 x64 container、zh-CN、PowerShell 5.1、.NET Framework 4.8。使用系统 Framework v4.0.30319 编译器，C# 5，产物必须为 x86。无外部包，无 shell/网络工具。只有 src/EvidenceMirror/**/*.cs 可写（允许新增）；构建入口、校准数据和其他文件不可改。build 工具编译当前全部源文件；inspect_inputs 可读取当前独立输入的可观察清单，run_case 可运行当前候选 seal/report（不会返回隐藏测试或评分）。edit_file 支持唯一精确片段替换，write_file 支持完整源码写入。没有本地 token 使用量配额；用量只作遥测。

每轮有独立工作区、输入和输出目录。具体路径由工具返回，不应硬编码盘符。输入只读，输出仅在本轮 staging 内。注册表基路径由环境变量 EVIDENCE_MIRROR_REGISTRY_ROOT 提供，位于 HKLM\\SOFTWARE\\Northgate\\EvidenceMirrorBench\\windows-d6-0007\\<run-id>；基线的 RootKeyPath 已读取该配置。监控服务读取此基路径的原生 64 位视图 Cases\\<CaseId>，不是当前 x86 进程的默认视图。不得访问其他轮次或任务的状态。

## 公开行为
- seal --case <id> --source <folder> --dest <folder>：成功退出 0，严格四行依次为 CaseId、FileCount、RootHash、MirrorRoot，以等号连接。MirrorRoot 必须逐字符保留参数。
- report --case <id>：成功退出 0，前四行同上，第五行为 CompletedUtc，使用可往返的 UTC ISO 8601；无记录退出 4。无参数/缺参数/未知动词退出 2；封存失败退出 3。
- 每个文件的全部主流和命名流、文件名、所有者、DACL（含保护和继承状态）、SACL 审计规则、创建/最后写入 UTC、稀疏/压缩属性和存储形态、硬链接关系及链接数均保持。文件 ID 数值、物理簇、访问时间、空目录和重解析点不在范围。
- 长路径、2,200,000,000 字节稀疏录像必须在 x86 地址空间中正确处理，不截断、不遗漏；文件计数包括硬链接各名字。
- 目标可以不存在，也可以带旧内容；成功后文件集合恰好等于源。重复 seal 的内容、FileCount、RootHash 相同。
- 一次 seal 必须整体完成：读取、复制、目标替换或记录发布失败，原目标和原记录保持不变；原来没有目标/记录就不能留下半成品。不留本次临时目录，不修改源。目标不是源的祖先或后代，同一案卷不并发封存。单案 seal 不要求强制杀进程恢复；seal-batch 必须满足 BATCH-CONTRACT.md 的强制终止及跨进程恢复要求，均不要求断电恢复。
- 权威记录只能有一份：在上述 HKLM 原生64视图的 Cases\\<CaseId> 下，FileCount 为 DWORD，其余 RootHash/MirrorRoot/CompletedUtc 为 REG_SZ；恰好这四个值。移除本案重定向32视图的陈旧记录，不能动别的案卷。report 从同一权威位置读取。
- 普通 CASE-1000 保留文件数量、内容和 CLI，摘要统一使用以下协议。源不存在必须干净失败、无目标、无记录。

SACL 保留包括审计主体、访问掩码、成功/失败审计标志、继承/传播标志、显式/继承状态及 SACL 保护状态。同样，DACL 的显式/继承 ACE 状态不能被只保留权限掩码替代。输入的硬链接组全部名称位于源案卷内，不要求重建案卷外的链接名。运行账户为本机管理员，具备启用备份、还原和安全审计所需的 Windows 特权；不得借此访问其他轮次或题目的数据。允许不同 Win32/Framework 实现，只验证公开可观察结果。

## 输入
run_batch 提供公开的普通/现场两案计划，支持 seal-batch、recover、batch-status。使用新的 sample 名创建独立旧目标；复用同一 sample 查询/恢复。可指定 BATCH-CONTRACT.md 的 checkpoint 让工具在真实回执后终止进程，再从新进程 recover。工具返回实际 CLI 和目标文件名，不提供隐藏评分。

CASE-1000 是普通案卷；CASE-2231 包括深路径、ADS、外部所有者、保护 DACL、审计规则、稀疏录像、压缩文件和硬链接。CASE-2232 可用于交接中读取失败场景。两份校准案卷 CASE-0100/0200 的已知摘要在 calibration/expected.json，只是公开协议的实例，不是穷举答案。input_manifest.json 是实际输入清单，不是隐藏断言。

## 完整验收契约

摘要规则是公开业务协议，不要求从哈希输出猜算法：
1. 每个文件枚举主流和所有命名数据流；取 FindFirstStreamW 名称并只移除第一个冒号。因此主流名是 `:$DATA`，命名流如 `Northgate.Chain:$DATA`。
2. 对每个流原始字节求 SHA256，编码为 64 位小写十六进制。按流发布名称的 `StringComparer.Ordinal` 排序，拼接 `流名|流摘要\n`；每条都以单独 LF 结尾，编码 UTF-8（无 BOM），再求 SHA256 得到文件摘要。
3. 相对文件路径以反斜杠分隔，不加根前缀，保留字面大小写；按 `StringComparer.Ordinal` 排序。拼接 `相对路径|文件摘要\n`，同样 UTF-8、LF、SHA256 得到 RootHash。无 Unicode 规范化，不使用当前文化排序。
4. 所有案卷（含 CASE-1000）统一采用本规则。CASE-1000 保持文件内容、数量和 CLI 兼容性；旧版本错误算法产生的 RootHash 不要求保持不变。校准记录是例子和自检输入，不是规则的唯一来源。

“NTFS 等价”只要求以下可观察项，不要求源与副本的文件 ID 数值、物理簇位置或最后访问时间相同：全部文件名/主流字节/命名流名称与字节；所有者、DACL 及保护/继承状态；SACL 审计规则；创建和最后写入 UTC 时间；稀疏及压缩属性和实际存储形态；文件之间的硬链接关系及链接数。现场稀疏录像实际分配不超过 4,194,304 字节；压缩夹具实际分配不超过逻辑体积的 1/4，允许 Windows lazy writer 最多 60 秒完成只读观测。文件数量包括各硬链接名字。其它契约（32 位产物、长路径、原子失败、注册表双视图）仍适用。

公开调试补充：run_public_failure 在普通小案卷上制造权威注册表发布拒绝，返回 CLI、旧目标与两视图旧记录的前后观察；它不调用隐藏评测。失败回滚必须保留原有两视图记录，不能把“发布未完成”当成“原记录不存在”并删除它。先用 run_case 验证单案，再用 run_batch 验证正常及崩溃恢复，最后用此工具验证失败路径。
