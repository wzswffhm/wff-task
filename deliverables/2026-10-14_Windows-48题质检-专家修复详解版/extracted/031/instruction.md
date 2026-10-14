请修复 workspace/candidate.ps1，参数为 -Path、-Hidden、-ReadOnly。只修改指定普通文件的 Hidden 和 ReadOnly 属性，两个参数均为布尔值；必须保留该文件已有的 Archive、System 以及其他属性。返回对象包含 Status="updated"。路径按字面处理，不得使用通配符，不得改动其他文件或目录。

支持已有普通文件。

真实环境：Windows Server 2022 x64（20348）、PowerShell 7.5.10、NTFS。只修改工作区 candidate.ps1，保持参数入口；离线运行，不输出额外日志。
