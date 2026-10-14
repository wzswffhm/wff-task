我们有个更新小工具，同一份文件有时会被 NTFS 硬链接引用。请修好 workspace/candidate.ps1，参数是 -Path 和 -Text。把指定路径的内容更新为 Text 的 UTF-8（不带 BOM）字节，但其他硬链接必须保留原来的内容；指定路径本身仍是一个普通文件。文件名可能有空格、中文或方括号，不能按通配符解释。不存在的路径应创建文件。不要动同目录的其他文件，返回对象应包含 Status="updated"。只需要支持当前用户可写的 NTFS 本地目录，不处理目录或重解析点。

运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。
