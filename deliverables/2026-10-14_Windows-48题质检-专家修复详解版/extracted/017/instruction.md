请修好 workspace/candidate.ps1，用 -Root 扫描一个本地 NTFS 目录，返回一个包含 Files 属性的对象。Files 是根目录下所有普通 .log 文件的相对路径数组，扩展名不区分大小写，路径使用反斜杠，按 OrdinalIgnoreCase 排序。需要递归普通子目录，文件名按字面处理。目录树中可能存在 junction、目录符号链接、循环链接；所有重解析点都必须跳过，包括指向根目录内部的链接。不能访问链接目标或改动任何文件。空目录返回空数组，Root 自身必须是一个普通目录。

运行环境是 Windows Server 2022 x64（20348）、PowerShell 7.5.10 和 NTFS，本题离线运行。只修改 workspace/candidate.ps1，保持上述参数入口，不输出额外日志。
