请修复 workspace/candidate.ps1，参数为 -SubKey、-Action Set|Get|Remove、-Value。SubKey 是 HKCU 下相对路径。Set 将 Value 写入该键的默认值（空名称），返回 Status="set"；Get 返回 Status="found"、Value，不存在返回 Status="missing"；Remove 幂等。必须保留同一键上的其他命名值和子键，只允许写 HKCU。

Value 允许为空字符串；空默认值属于 found，缺少默认值属于 missing。Remove 只删除默认值，成功及重复调用可返回 removed 或 missing。

真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。
