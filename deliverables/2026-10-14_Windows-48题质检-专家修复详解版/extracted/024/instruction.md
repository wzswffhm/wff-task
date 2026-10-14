请修复 workspace/candidate.ps1，管理当前用户可写普通文件的 NTFS 备用数据流。参数为 -Path、-Stream、-Action Set|Get|Remove、-Value。Set 写入 UTF-8 无 BOM 文本并返回 Status="set"；Get 返回 Status="found"、Value，不存在返回 Status="missing"；Remove 幂等返回 Status="removed" 或 "missing"。主文件内容、其他数据流和文件名必须保持不变，不得把数据流内容写进主文件。

Path 指向已有普通文件；Stream 是非空、不含冒号和目录分隔符的自定义流名称。空 Value 表示存在的空数据流。Set 覆盖旧内容，删除后 Get 返回 missing。

真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。
